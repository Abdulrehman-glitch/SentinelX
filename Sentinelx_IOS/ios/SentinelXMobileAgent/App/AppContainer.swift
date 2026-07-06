import Foundation

/// Composition root. Builds every service once at launch and hands them to
/// ViewModels through factory methods, so nothing reaches for globals.
@MainActor
final class AppContainer: ObservableObject {
    let environment: AppEnvironment
    let keychain: KeychainStoring
    let tokenStore: TokenStore
    let deviceSecretStore: DeviceSecretStore
    let apiClient: APIClient
    let deviceInfoProvider: DeviceInfoProviding
    let registrationService: DeviceRegistrationService
    let authService: AuthService
    let configurationService: ConfigurationService
    let collectorRegistry: CollectorRegistry
    let telemetryManager: TelemetryManager
    let telemetryQueue: TelemetryQueue
    let webSocketClient: WebSocketClient
    let syncManager: SyncManager

    init(environment: AppEnvironment = .load()) {
        self.environment = environment

        let keychain = KeychainStore()
        self.keychain = keychain

        let tokenStore = TokenStore(keychain: keychain)
        self.tokenStore = tokenStore

        let deviceSecretStore = DeviceSecretStore(keychain: keychain)
        self.deviceSecretStore = deviceSecretStore

        let apiClient = APIClient(
            environment: environment,
            transport: URLSessionTransport(),
            tokenStore: tokenStore,
            deviceSecretStore: deviceSecretStore
        )
        self.apiClient = apiClient

        let deviceInfoProvider = UIKitDeviceInfoProvider()
        self.deviceInfoProvider = deviceInfoProvider

        let registrationService = DeviceRegistrationService(
            apiClient: apiClient,
            deviceSecretStore: deviceSecretStore,
            deviceInfoProvider: deviceInfoProvider,
            environment: environment
        )
        self.registrationService = registrationService

        self.authService = AuthService(
            apiClient: apiClient,
            tokenStore: tokenStore,
            deviceSecretStore: deviceSecretStore,
            registrationService: registrationService
        )

        let configurationService = ConfigurationService(apiClient: apiClient)
        self.configurationService = configurationService

        // Essential collectors (Phase 3). Motion/location/bluetooth/
        // MetricKit follow in Phases 6-7.
        let collectorRegistry = CollectorRegistry(collectors: [
            DeviceCollector(deviceInfoProvider: deviceInfoProvider),
            BatteryCollector(),
            ThermalCollector(),
            StorageCollector(),
            NetworkCollector(),
        ])
        self.collectorRegistry = collectorRegistry

        let telemetryManager = TelemetryManager(
            registry: collectorRegistry,
            configurationService: configurationService,
            deviceSecretStore: deviceSecretStore,
            environment: environment
        )
        self.telemetryManager = telemetryManager

        // Durable offline queue (Phase 5). If Application Support can't be
        // opened the in-memory fallback keeps the agent running —
        // durability is lost, but sqlite can't realistically refuse :memory:.
        let telemetryQueue: TelemetryQueue
        do {
            telemetryQueue = try TelemetryQueue(path: TelemetryQueue.defaultPath())
        } catch {
            Log.telemetry.error("Offline queue unavailable, using in-memory fallback: \(String(describing: error), privacy: .public)")
            telemetryQueue = try! TelemetryQueue(path: ":memory:")
        }
        self.telemetryQueue = telemetryQueue

        let webSocketClient = WebSocketClient(
            environment: environment,
            deviceSecretStore: deviceSecretStore,
            tokenProvider: apiClient
        )
        self.webSocketClient = webSocketClient

        self.syncManager = SyncManager(
            telemetryManager: telemetryManager,
            stream: webSocketClient,
            uploader: apiClient,
            queue: telemetryQueue,
            deviceSecretStore: deviceSecretStore
        )
    }

    /// Brings the whole agent up (or down) as one unit: collectors,
    /// WebSocket, and the sync pipeline.
    func startAgent() async {
        await syncManager.start()
        await webSocketClient.start()
        await telemetryManager.start()
    }

    func stopAgent() async {
        await telemetryManager.stop()
        await webSocketClient.stop()
        await syncManager.stop()
    }

    func makeAuthViewModel() -> AuthViewModel {
        AuthViewModel(authService: authService, environment: environment)
    }

    func makeTelemetryDebugViewModel() -> TelemetryDebugViewModel {
        TelemetryDebugViewModel(telemetryManager: telemetryManager)
    }
}
