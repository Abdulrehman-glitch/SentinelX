import Foundation
import Network

/// Emits `network.status` on every network path change via NWPathMonitor.
/// Interface-level reachability only — no scanning or traffic capture.
actor NetworkCollector: TelemetryCollector {
    nonisolated let id = "network"
    nonisolated let category = TelemetryCategory.network

    private var context: TelemetryContext?
    private var emitter: (any TelemetryEmitting)?
    private var enabled = true
    private var running = false
    private var monitor: NWPathMonitor?
    private var lastEvent: TelemetryEvent?
    private var lastPayload: NetworkPayload?
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

        let monitor = NWPathMonitor()
        self.monitor = monitor
        monitor.pathUpdateHandler = { path in
            // Convert to a Sendable payload before crossing into the actor.
            let payload = Self.makePayload(from: path)
            Task { [weak self] in await self?.handle(payload) }
        }
        monitor.start(queue: DispatchQueue(label: "com.sentinelx.networkcollector"))
        Log.collectors.info("NetworkCollector started")
    }

    func stop() {
        guard running else { return }
        running = false
        monitor?.cancel()
        monitor = nil
        Log.collectors.info("NetworkCollector stopped")
    }

    func latestValue() -> TelemetryEvent? { lastEvent }

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

    private static func makePayload(from path: NWPath) -> NetworkPayload {
        let reachable = path.status == .satisfied
        let interface: NetworkInterface
        if !reachable {
            interface = .unavailable
        } else if path.usesInterfaceType(.wifi) {
            interface = .wifi
        } else if path.usesInterfaceType(.cellular) {
            interface = .cellular
        } else if path.usesInterfaceType(.wiredEthernet) {
            interface = .wiredEthernet
        } else if path.usesInterfaceType(.loopback) {
            interface = .loopback
        } else {
            interface = .other
        }
        return NetworkPayload(
            reachable: reachable,
            interface: interface,
            expensive: path.isExpensive,
            constrained: path.isConstrained
        )
    }

    private func handle(_ payload: NetworkPayload) async {
        guard running, let context, let emitter else { return }
        guard payload != lastPayload else { return }

        do {
            let event = context.makeEvent(
                category: category,
                type: "network.status",
                source: "ios.network",
                payload: try JSONValue(encoding: payload)
            )
            lastPayload = payload
            lastEvent = event
            lastError = nil
            await emitter.emit(event)
        } catch {
            lastError = "Failed to encode network payload"
        }
    }
}
