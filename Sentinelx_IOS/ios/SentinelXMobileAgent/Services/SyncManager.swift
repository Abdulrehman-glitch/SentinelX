import Foundation

/// REST upload surface SyncManager needs (APIClient conforms).
protocol TelemetryUploading: Sendable {
    func uploadTelemetryBatch(_ request: TelemetryBatchRequest) async throws -> BatchUploadResponse
}

struct SyncStats: Equatable, Sendable {
    var sentViaStream = 0
    var sentViaBatch = 0
    var rejectedByServer = 0
    var dropped = 0
    var pendingCount = 0
}

/// Phase 4 upload pipeline: subscribes to TelemetryManager's event stream,
/// pushes each event over the WebSocket, and falls back to buffered REST
/// batches when the stream is down. The in-memory buffer is a stopgap —
/// Phase 5 replaces it with the SQLite offline queue.
actor SyncManager {
    private let telemetryManager: TelemetryManager
    private let stream: TelemetryStreaming
    private let uploader: TelemetryUploading
    private let deviceSecretStore: DeviceSecretStore
    private let uuidProvider: UUIDProviding
    private let dateProvider: DateProviding
    private let flushInterval: TimeInterval
    private let batchSize: Int
    private let maxPending: Int

    private var pending: [TelemetryEvent] = []
    private var consumeTask: Task<Void, Never>?
    private var flushTask: Task<Void, Never>?
    private var flushing = false
    private(set) var stats = SyncStats()

    init(
        telemetryManager: TelemetryManager,
        stream: TelemetryStreaming,
        uploader: TelemetryUploading,
        deviceSecretStore: DeviceSecretStore,
        uuidProvider: UUIDProviding = SystemUUIDProvider(),
        dateProvider: DateProviding = SystemDateProvider(),
        flushInterval: TimeInterval = TimeInterval(AppConstants.defaultFlushIntervalSeconds),
        batchSize: Int = AppConstants.defaultBatchSize,
        maxPending: Int = 1000
    ) {
        self.telemetryManager = telemetryManager
        self.stream = stream
        self.uploader = uploader
        self.deviceSecretStore = deviceSecretStore
        self.uuidProvider = uuidProvider
        self.dateProvider = dateProvider
        self.flushInterval = flushInterval
        self.batchSize = batchSize
        self.maxPending = maxPending
    }

    func start() async {
        guard consumeTask == nil else { return }
        consumeTask = Task { [telemetryManager] in
            for await event in await telemetryManager.eventStream() {
                await self.handle(event)
            }
        }
        flushTask = Task {
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(self.flushInterval))
                guard !Task.isCancelled else { break }
                await self.flushPending()
            }
        }
        Log.telemetry.info("SyncManager started")
    }

    func stop() async {
        consumeTask?.cancel()
        consumeTask = nil
        flushTask?.cancel()
        flushTask = nil
        await flushPending() // last chance for buffered events this session
        Log.telemetry.info("SyncManager stopped")
    }

    // MARK: - Pipeline

    private func handle(_ event: TelemetryEvent) async {
        do {
            try await stream.send(event)
            stats.sentViaStream += 1
        } catch {
            enqueue(event)
            if pending.count >= batchSize {
                await flushPending()
            }
        }
    }

    private func enqueue(_ event: TelemetryEvent) {
        pending.append(event)
        if pending.count > maxPending {
            let overflow = pending.count - maxPending
            pending.removeFirst(overflow)
            stats.dropped += overflow
        }
        stats.pendingCount = pending.count
    }

    /// Uploads the buffer in batch-size chunks. On a transport failure the
    /// remaining events stay buffered; the next flush tick retries them —
    /// idempotency by event_id makes re-sends safe.
    func flushPending() async {
        guard !flushing, !pending.isEmpty else { return }
        guard let identity = await deviceSecretStore.identity() else { return }
        flushing = true
        defer {
            flushing = false
            stats.pendingCount = pending.count
        }

        while !pending.isEmpty {
            let chunk = Array(pending.prefix(batchSize))
            let request = TelemetryBatchRequest(
                deviceId: identity.deviceId,
                batchId: uuidProvider.uuid(),
                sentAt: dateProvider.now(),
                events: chunk
            )
            do {
                let response = try await uploader.uploadTelemetryBatch(request)
                let chunkIds = Set(chunk.map(\.eventId))
                pending.removeAll { chunkIds.contains($0.eventId) }
                stats.sentViaBatch += response.acceptedCount
                stats.rejectedByServer += response.rejectedCount
                if response.rejectedCount > 0 {
                    Log.network.warning("Batch \(response.batchId, privacy: .public): \(response.rejectedCount) events rejected")
                }
            } catch {
                Log.network.warning("Batch flush failed, \(self.pending.count) events kept: \(String(describing: error), privacy: .public)")
                break
            }
        }
    }
}
