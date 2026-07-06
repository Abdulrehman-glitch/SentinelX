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

        let collectorRegistry = CollectorRegistry()
        self.collectorRegistry = collectorRegistry

        self.telemetryManager = TelemetryManager(
            registry: collectorRegistry,
            configurationService: configurationService,
            deviceSecretStore: deviceSecretStore,
            environment: environment
        )
    }

    func makeAuthViewModel() -> AuthViewModel {
        AuthViewModel(authService: authService, environment: environment)
    }

    func makeTelemetryDebugViewModel() -> TelemetryDebugViewModel {
        TelemetryDebugViewModel(telemetryManager: telemetryManager)
    }
}
