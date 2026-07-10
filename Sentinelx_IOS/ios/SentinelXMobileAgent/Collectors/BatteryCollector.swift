import UIKit

/// Polls battery level/state every `interval_seconds` (default 30) and
/// reacts to level, state and Low Power Mode notifications. In Low Power
/// Mode the poll interval is doubled to reduce the agent's own drain.
actor BatteryCollector: TelemetryCollector {
    nonisolated let id = "battery"
    nonisolated let category = TelemetryCategory.battery

    private var context: TelemetryContext?
    private var emitter: (any TelemetryEmitting)?
    private var enabled = true
    private var intervalSeconds = 30
    private var running = false
    private var pollTask: Task<Void, Never>?
    private var observers: [NSObjectProtocol] = []
    private var lastEvent: TelemetryEvent?
    private var lastPayload: BatteryPayload?
    private var lastError: String?

    func prepare(context: TelemetryContext, emitter: any TelemetryEmitting) {
        self.context = context
        self.emitter = emitter
    }

    func apply(_ config: CollectorConfig) async {
        enabled = config.enabled
        if let interval = config.intervalSeconds {
            intervalSeconds = max(5, interval)
        }
        if !enabled && running {
            await stop()
        }
    }

    func isEnabled() -> Bool { enabled }

    func start() async {
        guard enabled, !running, context != nil else { return }
        running = true

        await MainActor.run { UIDevice.current.isBatteryMonitoringEnabled = true }

        for name in [
            UIDevice.batteryLevelDidChangeNotification,
            UIDevice.batteryStateDidChangeNotification,
            Notification.Name.NSProcessInfoPowerStateDidChange,
        ] {
            let token = NotificationCenter.default.addObserver(forName: name, object: nil, queue: nil) { _ in
                Task { [weak self] in await self?.capture(onlyIfChanged: true) }
            }
            observers.append(token)
        }

        pollTask = Task { [weak self] in
            while !Task.isCancelled {
                await self?.capture(onlyIfChanged: false)
                let interval = await self?.currentPollInterval() ?? 30
                try? await Task.sleep(for: .seconds(interval))
            }
        }
        Log.collectors.info("BatteryCollector started")
    }

    func stop() async {
        guard running else { return }
        running = false
        pollTask?.cancel()
        pollTask = nil
        observers.forEach(NotificationCenter.default.removeObserver)
        observers.removeAll()
        await MainActor.run { UIDevice.current.isBatteryMonitoringEnabled = false }
        Log.collectors.info("BatteryCollector stopped")
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

    private func currentPollInterval() -> Int {
        ProcessInfo.processInfo.isLowPowerModeEnabled ? intervalSeconds * 2 : intervalSeconds
    }

    private func capture(onlyIfChanged: Bool) async {
        guard running, let context, let emitter else { return }
        guard let payload = await Self.readBattery() else {
            // Simulator without a simulated battery, or monitoring disabled.
            lastError = "Battery level unavailable"
            return
        }
        if onlyIfChanged && payload == lastPayload { return }

        do {
            let event = context.makeEvent(
                category: category,
                type: "battery.snapshot",
                source: "ios.uidevice",
                payload: try JSONValue(encoding: payload)
            )
            lastPayload = payload
            lastEvent = event
            lastError = nil
            await emitter.emit(event)
        } catch {
            lastError = "Failed to encode battery payload"
        }
    }

    @MainActor
    private static func readBattery() -> BatteryPayload? {
        let device = UIDevice.current
        let rawLevel = device.batteryLevel
        guard rawLevel >= 0 else { return nil }

        let state: BatteryState
        switch device.batteryState {
        case .unplugged: state = .unplugged
        case .charging: state = .charging
        case .full: state = .full
        default: state = .unknown
        }

        return BatteryPayload(
            level: Int((rawLevel * 100).rounded()),
            charging: state == .charging || state == .full,
            state: state,
            lowPowerMode: ProcessInfo.processInfo.isLowPowerModeEnabled
        )
    }
}
