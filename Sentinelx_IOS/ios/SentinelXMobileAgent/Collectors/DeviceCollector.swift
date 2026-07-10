import UIKit

/// Emits a `device.snapshot` on start and whenever the app returns to the
/// foreground — static facts change rarely, so no polling.
actor DeviceCollector: TelemetryCollector {
    nonisolated let id = "device"
    nonisolated let category = TelemetryCategory.device

    private let deviceInfoProvider: DeviceInfoProviding
    private var context: TelemetryContext?
    private var emitter: (any TelemetryEmitting)?
    private var enabled = true
    private var running = false
    private var observers: [NSObjectProtocol] = []
    private var lastEvent: TelemetryEvent?
    private var lastError: String?

    init(deviceInfoProvider: DeviceInfoProviding) {
        self.deviceInfoProvider = deviceInfoProvider
    }

    func prepare(context: TelemetryContext, emitter: any TelemetryEmitting) {
        self.context = context
        self.emitter = emitter
    }

    func apply(_ config: CollectorConfig) async {
        enabled = config.enabled
        if !enabled && running {
            await stop()
        }
    }

    func isEnabled() -> Bool { enabled }

    func start() async {
        guard enabled, !running, context != nil else { return }
        running = true

        let token = NotificationCenter.default.addObserver(
            forName: UIApplication.willEnterForegroundNotification,
            object: nil,
            queue: nil
        ) { _ in
            Task { [weak self] in await self?.captureSnapshot() }
        }
        observers.append(token)

        await captureSnapshot()
        Log.collectors.info("DeviceCollector started")
    }

    func stop() {
        guard running else { return }
        running = false
        observers.forEach(NotificationCenter.default.removeObserver)
        observers.removeAll()
        Log.collectors.info("DeviceCollector stopped")
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

    private func captureSnapshot() async {
        guard running, let context, let emitter else { return }
        let info = await deviceInfoProvider.snapshot()
        let payload = DevicePayload(
            deviceName: info.deviceName,
            deviceModel: info.deviceModel,
            systemName: info.systemName,
            systemVersion: info.systemVersion,
            locale: info.localeIdentifier,
            timezone: info.timezoneIdentifier,
            screenWidth: info.screenWidth,
            screenHeight: info.screenHeight,
            screenScale: info.screenScale
        )
        do {
            let event = context.makeEvent(
                category: category,
                type: "device.snapshot",
                source: "ios.uikit",
                payload: try JSONValue(encoding: payload)
            )
            lastEvent = event
            lastError = nil
            await emitter.emit(event)
        } catch {
            lastError = "Failed to encode device payload"
        }
    }
}
