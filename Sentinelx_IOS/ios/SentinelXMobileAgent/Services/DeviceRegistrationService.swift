import Foundation

/// One-time device enrolment: builds the registration payload from live
/// device info, calls the backend, and locks the returned device secret
/// away in the Keychain.
final class DeviceRegistrationService: Sendable {
    private let apiClient: APIClient
    private let deviceSecretStore: DeviceSecretStore
    private let deviceInfoProvider: DeviceInfoProviding
    private let environment: AppEnvironment

    init(
        apiClient: APIClient,
        deviceSecretStore: DeviceSecretStore,
        deviceInfoProvider: DeviceInfoProviding,
        environment: AppEnvironment
    ) {
        self.apiClient = apiClient
        self.deviceSecretStore = deviceSecretStore
        self.deviceInfoProvider = deviceInfoProvider
        self.environment = environment
    }

    func registerIfNeeded() async throws -> DeviceIdentity {
        if let identity = await deviceSecretStore.identity() {
            return identity
        }

        let info = await deviceInfoProvider.snapshot()
        let request = DeviceRegistrationRequest(
            platform: .ios,
            deviceName: info.deviceName,
            deviceModel: info.deviceModel,
            osVersion: "\(info.systemName) \(info.systemVersion)",
            appVersion: environment.agentVersion,
            vendorIdentifier: info.vendorIdentifier,
            timezone: info.timezoneIdentifier,
            locale: info.localeIdentifier
        )

        let response = try await apiClient.register(request)
        let identity = DeviceIdentity(deviceId: response.deviceId, deviceSecret: response.deviceSecret)
        try await deviceSecretStore.save(identity)
        Log.auth.info("Device registered as \(response.deviceId, privacy: .public)")
        return identity
    }
}
