import Foundation

/// REST upload surface SyncManager needs (APIClient conforms).
protocol TelemetryUploading: Sendable {
    func uploadTelemetryBatch(_ request: TelemetryBatchRequest) async throws -> BatchUploadResponse
}

struct SyncStats: Equatable, Sendable {
    var sentViaStream = 0
    var sentViaBatch = 0
    var rejectedByServer = 0
    var ackedViaStream = 0
}

/// Phase 5 upload pipeline (docs/spec/04 §25): every event is persisted to
/// the SQLite queue before any network attempt. Drains send single events
/// over the WebSocket while it's up and REST batches otherwise. Stream
/// sends stay `in_flight` until the server's `telemetry.ack` deletes them;
/// unacknowledged sends are requeued on disconnect or relaunch — the
/// server's event_id idempotency makes re-sends safe (at-least-once).
actor SyncManager {
    private let telemetryManager: TelemetryManager
    private let stream: TelemetryStreaming
    private let uploader: TelemetryUploading
    private let queue: TelemetryQueue
    private let deviceSecretStore: DeviceSecretStore
    private let uuidProvider: UUIDProviding
    private let dateProvider: DateProviding
    private let flushInterval: TimeInterval
    private let batchSize: Int
    private let retryPolicy: RetryPolicy
    private let consumeStreamAcks: Bool

    private var consumeTask: Task<Void, Never>?
    private var connectionTask: Task<Void, Never>?
    private var ackTask: Task<Void, Never>?
    private var flushTask: Task<Void, Never>?
    private var draining = false
    private var drainRequestedWhileBusy = false
    private var failedDrains = 0
    private var resumeDrainsAt: Date?
    private(set) var streamConnected = false
    private(set) var stats = SyncStats()

    init(
        telemetryManager: TelemetryManager,
        stream: TelemetryStreaming,
        uploader: TelemetryUploading,
        queue: TelemetryQueue,
        deviceSecretStore: DeviceSecretStore,
        uuidProvider: UUIDProviding = SystemUUIDProvider(),
        dateProvider: DateProviding = SystemDateProvider(),
        flushInterval: TimeInterval = TimeInterval(AppConstants.defaultFlushIntervalSeconds),
        batchSize: Int = AppConstants.defaultBatchSize,
        retryPolicy: RetryPolicy = .upload,
        consumeStreamAcks: Bool = true
    ) {
        self.telemetryManager = telemetryManager
        self.stream = stream
        self.uploader = uploader
        self.queue = queue
        self.deviceSecretStore = deviceSecretStore
        self.uuidProvider = uuidProvider
        self.dateProvider = dateProvider
        self.flushInterval = flushInterval
        self.batchSize = batchSize
        self.retryPolicy = retryPolicy
        self.consumeStreamAcks = consumeStreamAcks
    }

    func start() async {
        guard consumeTask == nil else { return }
        // Unacknowledged sends from the previous run go again (spec 04 §25).
        try? await queue.requeueInFlight()
        // Subscribe before returning — deferring it into the Tasks would
        // race events emitted right after startup.
        let events = await telemetryManager.eventStream()
        let connections = await stream.connectionEvents()
        consumeTask = Task {
            for await event in events {
                await self.ingest(event)
            }
        }
        connectionTask = Task {
            for await change in connections {
                await self.handleConnection(change)
            }
        }
        if consumeStreamAcks {
            let messages = await stream.serverMessages()
            ackTask = Task {
                for await message in messages {
                    guard case .telemetryAck(let eventIds, _) = message else { continue }
                    await self.handleAck(eventIds)
                }
            }
        }
        flushTask = Task {
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(self.flushInterval))
                guard !Task.isCancelled else { break }
                await self.drain(bypassingBackoff: false)
            }
        }
        Log.telemetry.info("SyncManager started")
    }

    func stop() async {
        consumeTask?.cancel()
        consumeTask = nil
        connectionTask?.cancel()
        connectionTask = nil
        ackTask?.cancel()
        ackTask = nil
        flushTask?.cancel()
        flushTask = nil
        await drain(bypassingBackoff: true) // best effort before shutdown
        Log.telemetry.info("SyncManager stopped")
    }

    /// Queue state for the inspection UI and tests.
    func queueCounts() async -> QueueCounts {
        (try? await queue.counts()) ?? QueueCounts()
    }

    func flushNow() async {
        await drain(bypassingBackoff: true)
    }

    // MARK: - Pipeline

    private func ingest(_ event: TelemetryEvent) async {
        do {
            try await queue.enqueue(event) // durable before any send attempt
        } catch {
            Log.telemetry.error("Enqueue failed, event dropped: \(String(describing: error), privacy: .public)")
            return
        }
        if streamConnected {
            await drain(bypassingBackoff: false) // live path: ship immediately
        } else if let counts = try? await queue.counts(), counts.pending >= batchSize {
            await drain(bypassingBackoff: false)
        }
    }

    /// Acknowledged stream sends leave the queue for good (spec 04 §25:
    /// delete only after acknowledgement). Deleting by event_id is
    /// idempotent, so acks that race a reconnect-requeue are harmless.
    private func handleAck(_ eventIds: [UUID]) async {
        guard !eventIds.isEmpty else { return }
        try? await queue.markUploaded(eventIds)
        stats.ackedViaStream += eventIds.count
    }

    private func handleConnection(_ change: StreamConnectionEvent) async {
        switch change {
        case .connected:
            streamConnected = true
            failedDrains = 0
            resumeDrainsAt = nil
            await drain(bypassingBackoff: false)
        case .disconnected:
            streamConnected = false
            // No WS ack yet (P5.3): sends on the dying socket may be lost,
            // so everything unacknowledged goes back to pending.
            try? await queue.requeueInFlight()
        }
    }

    /// Drains the queue in FIFO batches until it's empty or the transport
    /// fails. Failed drains back off per RetryPolicy.upload; a drain
    /// requested while one is running re-runs the loop instead of being
    /// dropped.
    private func drain(bypassingBackoff: Bool) async {
        if draining {
            drainRequestedWhileBusy = true
            return
        }
        if !bypassingBackoff, let resumeAt = resumeDrainsAt, dateProvider.now() < resumeAt {
            return
        }
        guard let identity = await deviceSecretStore.identity() else { return }
        draining = true
        defer { draining = false }

        repeat {
            drainRequestedWhileBusy = false
            await drainOnce(deviceId: identity.deviceId)
        } while drainRequestedWhileBusy
    }

    private func drainOnce(deviceId: String) async {
        while true {
            guard let batch = try? await queue.nextBatch(limit: batchSize), !batch.isEmpty else {
                return
            }

            var remaining = batch
            if streamConnected {
                while let event = remaining.first {
                    do {
                        try await stream.send(event)
                        stats.sentViaStream += 1
                        remaining.removeFirst()
                    } catch {
                        break // stream died mid-batch — REST takes the rest
                    }
                }
            }
            if remaining.isEmpty {
                // Stream-sent events stay in_flight until the ack (P5.3).
                recordDrainSuccess()
                continue
            }

            let request = TelemetryBatchRequest(
                deviceId: deviceId,
                batchId: uuidProvider.uuid(),
                sentAt: dateProvider.now(),
                events: remaining
            )
            do {
                let response = try await uploader.uploadTelemetryBatch(request)
                var rejectedReasons: [UUID: String] = [:]
                for rejected in response.rejectedEvents {
                    guard let id = UUID(uuidString: rejected.eventId) else { continue }
                    rejectedReasons[id] = rejected.reason
                    try? await queue.markFailed([id], error: rejected.reason)
                }
                let uploadedIds = remaining.map(\.eventId).filter { rejectedReasons[$0] == nil }
                try? await queue.markUploaded(uploadedIds)
                stats.sentViaBatch += uploadedIds.count
                stats.rejectedByServer += rejectedReasons.count
                if !rejectedReasons.isEmpty {
                    Log.network.warning("Batch \(response.batchId, privacy: .public): \(rejectedReasons.count) events rejected permanently")
                }
                recordDrainSuccess()
            } catch {
                try? await queue.markForRetry(remaining.map(\.eventId), error: String(describing: error))
                failedDrains += 1
                let attempt = min(failedDrains, retryPolicy.maxAttempts ?? failedDrains)
                let delay = retryPolicy.delay(forAttempt: attempt) ?? retryPolicy.maxDelay
                resumeDrainsAt = dateProvider.now().addingTimeInterval(delay)
                Log.network.warning("Drain failed (attempt \(self.failedDrains)), next in \(delay, format: .fixed(precision: 0))s: \(String(describing: error), privacy: .public)")
                return
            }
        }
    }

    private func recordDrainSuccess() {
        failedDrains = 0
        resumeDrainsAt = nil
    }
}
