import Foundation

/// Central telemetry coordinator: prepares and starts collectors, validates
/// every emitted event, stamps the session sequence, keeps a recent-events
/// buffer for the debug UI, and fans events out to subscribers (the debug
/// UI and SyncManager, which persists them to the offline queue).
actor TelemetryManager: TelemetryEmitting {
    private let registry: CollectorRegistry
    private let configurationService: ConfigurationService
    private let deviceSecretStore: DeviceSecretStore
    private let environment: AppEnvironment
    private let uuidProvider: UUIDProviding
    private let dateProvider: DateProviding

    private var running = false
    private var expectedDeviceId: String?
    private var sequence = 0
    private var recentBuffer: [TelemetryEvent] = []
    private let recentLimit = 200
    private var subscribers: [UUID: AsyncStream<TelemetryEvent>.Continuation] = [:]

    private(set) var acceptedCount = 0
    private(set) var rejectedCount = 0

    init(
        registry: CollectorRegistry,
        configurationService: ConfigurationService,
        deviceSecretStore: DeviceSecretStore,
        environment: AppEnvironment,
        uuidProvider: UUIDProviding = SystemUUIDProvider(),
        dateProvider: DateProviding = SystemDateProvider()
    ) {
        self.registry = registry
        self.configurationService = configurationService
        self.deviceSecretStore = deviceSecretStore
        self.environment = environment
        self.uuidProvider = uuidProvider
        self.dateProvider = dateProvider
    }

    var isRunning: Bool { running }

    func start() async {
        guard !running else { return }
        guard let identity = await deviceSecretStore.identity() else {
            Log.telemetry.warning("TelemetryManager start skipped — device not registered")
            return
        }
        running = true
        expectedDeviceId = identity.deviceId

        let config = await configurationService.currentConfig()
        let context = TelemetryContext(
            deviceId: identity.deviceId,
            metadata: TelemetryMetadata(
                platform: .ios,
                agentVersion: environment.agentVersion,
                collectorVersion: "1.0.0",
                appBuild: environment.appBuild,
                environment: environment.environmentName
            ),
            uuidProvider: uuidProvider,
            dateProvider: dateProvider
        )

        for collector in await registry.allCollectors() {
            await collector.prepare(context: context, emitter: self)
            if let collectorConfig = config.collectors[collector.id] {
                await collector.apply(collectorConfig)
            }
            if await collector.isEnabled() {
                await collector.start()
            }
        }
        Log.telemetry.info("TelemetryManager started")
    }

    func stop() async {
        guard running else { return }
        running = false
        await registry.stopAll()
        Log.telemetry.info("TelemetryManager stopped")
    }

    // MARK: - TelemetryEmitting

    func emit(_ event: TelemetryEvent) async {
        guard running, let expectedDeviceId else { return }

        if let error = TelemetryEventValidator.validate(
            event,
            expectedDeviceId: expectedDeviceId,
            now: dateProvider.now()
        ) {
            rejectedCount += 1
            Log.telemetry.error("Rejected \(event.type, privacy: .public): \(String(describing: error), privacy: .public)")
            return
        }

        sequence += 1
        let stamped = event.withSequence(sequence)
        acceptedCount += 1

        recentBuffer.append(stamped)
        if recentBuffer.count > recentLimit {
            recentBuffer.removeFirst(recentBuffer.count - recentLimit)
        }
        for continuation in subscribers.values {
            continuation.yield(stamped)
        }
    }

    // MARK: - Consumers

    /// Newest-last snapshot of recently accepted events.
    func recentEvents() -> [TelemetryEvent] {
        recentBuffer
    }

    /// Independent live stream per subscriber (debug UI, SyncManager).
    func eventStream() -> AsyncStream<TelemetryEvent> {
        AsyncStream { continuation in
            let subscriberId = UUID()
            subscribers[subscriberId] = continuation
            continuation.onTermination = { _ in
                Task { await self.removeSubscriber(subscriberId) }
            }
        }
    }

    func healthReports() async -> [CollectorHealth] {
        await registry.healthReports()
    }

    private func removeSubscriber(_ id: UUID) {
        subscribers.removeValue(forKey: id)
    }
}
