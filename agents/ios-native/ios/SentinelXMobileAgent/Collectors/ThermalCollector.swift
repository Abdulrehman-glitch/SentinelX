import Foundation

/// Emits `thermal.state` on start and on every system thermal state change —
/// purely event-driven, no polling.
actor ThermalCollector: TelemetryCollector {
    nonisolated let id = "thermal"
    nonisolated let category = TelemetryCategory.thermal

    private var context: TelemetryContext?
    private var emitter: (any TelemetryEmitting)?
    private var enabled = true
    private var running = false
    private var observers: [NSObjectProtocol] = []
    private var lastEvent: TelemetryEvent?
    private var lastError: String?

    func prepare(context: TelemetryContext, emitter: any TelemetryEmitting) {
        self.context = context
        self.emitter = emitter
    }

    func apply(_ config: CollectorConfig) async {
        enabled = config.enabled
        if !enabled && running {
            stop()
        }
    }

    func isEnabled() -> Bool { enabled }

    func start() async {
        guard enabled, !running, context != nil else { return }
        running = true

        let token = NotificationCenter.default.addObserver(
            forName: ProcessInfo.thermalStateDidChangeNotification,
            object: nil,
            queue: nil
        ) { _ in
            Task { [weak self] in await self?.capture() }
        }
        observers.append(token)

        await capture()
        Log.collectors.info("ThermalCollector started")
    }

    func stop() {
        guard running else { return }
        running = false
        observers.forEach(NotificationCenter.default.removeObserver)
        observers.removeAll()
        Log.collectors.info("ThermalCollector stopped")
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

    /// Pure mapping, exposed for tests.
    static func map(_ state: ProcessInfo.ThermalState) -> ThermalState {
        switch state {
        case .nominal: return .nominal
        case .fair: return .fair
        case .serious: return .serious
        case .critical: return .critical
        @unknown default: return .unknown
        }
    }

    private func capture() async {
        guard running, let context, let emitter else { return }
        let payload = ThermalPayload(state: Self.map(ProcessInfo.processInfo.thermalState))
        do {
            let event = context.makeEvent(
                category: category,
                type: "thermal.state",
                source: "ios.processinfo",
                payload: try JSONValue(encoding: payload)
            )
            lastEvent = event
            lastError = nil
            await emitter.emit(event)
        } catch {
            lastError = "Failed to encode thermal payload"
        }
    }
}
