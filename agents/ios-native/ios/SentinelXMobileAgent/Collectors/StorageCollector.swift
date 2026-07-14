import Foundation

/// Polls volume capacity every `interval_seconds` (default 60), emitting
/// only when the reading changes — storage moves slowly and the query has
/// real I/O cost.
actor StorageCollector: TelemetryCollector {
    nonisolated let id = "storage"
    nonisolated let category = TelemetryCategory.storage

    private var context: TelemetryContext?
    private var emitter: (any TelemetryEmitting)?
    private var enabled = true
    private var intervalSeconds = 60
    private var running = false
    private var pollTask: Task<Void, Never>?
    private var lastEvent: TelemetryEvent?
    private var lastPayload: StoragePayload?
    private var lastError: String?

    func prepare(context: TelemetryContext, emitter: any TelemetryEmitting) {
        self.context = context
        self.emitter = emitter
    }

    func apply(_ config: CollectorConfig) async {
        enabled = config.enabled
        if let interval = config.intervalSeconds {
            intervalSeconds = max(15, interval)
        }
        if !enabled && running {
            stop()
        }
    }

    func isEnabled() -> Bool { enabled }

    func start() async {
        guard enabled, !running, context != nil else { return }
        running = true

        pollTask = Task { [weak self] in
            while !Task.isCancelled {
                await self?.capture()
                let interval = await self?.intervalSeconds ?? 60
                try? await Task.sleep(for: .seconds(interval))
            }
        }
        Log.collectors.info("StorageCollector started")
    }

    func stop() {
        guard running else { return }
        running = false
        pollTask?.cancel()
        pollTask = nil
        Log.collectors.info("StorageCollector stopped")
    }

    func healthStatus() -> CollectorHealth {
        CollectorHealth(
            collectorId: id,
            category: category,
            enabled: enabled,
            health: !enabled ? .disabled : (lastError != nil ? .degraded : .healthy),
            lastEventAt: lastEvent?.timestamp,
            errorMessage: lastError
        )
    }

    private func capture() async {
        guard running, let context, let emitter else { return }
        guard let payload = Self.readStorage() else {
            lastError = "Volume capacity unavailable"
            return
        }
        guard payload != lastPayload else { return }

        do {
            let event = context.makeEvent(
                category: category,
                type: "storage.snapshot",
                source: "ios.filemanager",
                payload: try JSONValue(encoding: payload)
            )
            lastPayload = payload
            lastEvent = event
            lastError = nil
            await emitter.emit(event)
        } catch {
            lastError = "Failed to encode storage payload"
        }
    }

    private static func readStorage() -> StoragePayload? {
        let url = URL(fileURLWithPath: NSHomeDirectory())
        guard
            let values = try? url.resourceValues(forKeys: [
                .volumeTotalCapacityKey,
                .volumeAvailableCapacityForImportantUsageKey,
            ]),
            let total = values.volumeTotalCapacity,
            let free = values.volumeAvailableCapacityForImportantUsage,
            total > 0
        else {
            return nil
        }

        let totalBytes = Int64(total)
        let freeBytes = min(free, totalBytes)
        let freePercent = (Double(freeBytes) / Double(totalBytes) * 1000).rounded() / 10
        return StoragePayload(
            totalBytes: totalBytes,
            freeBytes: freeBytes,
            usedBytes: totalBytes - freeBytes,
            freePercent: freePercent
        )
    }
}
