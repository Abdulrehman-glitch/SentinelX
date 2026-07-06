import Foundation

/// Session lifecycle: registration handoff, login, silent re-login, logout.
/// Publishes the session state that drives root navigation.
@MainActor
final class AuthService: ObservableObject {
    enum SessionState: Equatable, Sendable {
        case unknown
        case needsRegistration
        /// Device has credentials but no live session.
        case registered
        case authenticating
        case authenticated(deviceId: String)
    }

    @Published private(set) var state: SessionState = .unknown
    @Published private(set) var lastErrorMessage: String?

    private let apiClient: APIClient
    private let tokenStore: TokenStore
    private let deviceSecretStore: DeviceSecretStore
    private let registrationService: DeviceRegistrationService
    private let dateProvider: DateProviding
    private var bootstrapped = false

    init(
        apiClient: APIClient,
        tokenStore: TokenStore,
        deviceSecretStore: DeviceSecretStore,
        registrationService: DeviceRegistrationService,
        dateProvider: DateProviding = SystemDateProvider()
    ) {
        self.apiClient = apiClient
        self.tokenStore = tokenStore
        self.deviceSecretStore = deviceSecretStore
        self.registrationService = registrationService
        self.dateProvider = dateProvider
    }

    func bootstrapIfNeeded() async {
        guard !bootstrapped else { return }
        bootstrapped = true

        guard let identity = await deviceSecretStore.identity() else {
            state = .needsRegistration
            return
        }
        if await tokenStore.currentTokens() != nil {
            // A stale access token is fine — APIClient refreshes on demand.
            state = .authenticated(deviceId: identity.deviceId)
        } else {
            await login()
        }
    }

    func registerAndLogin() async {
        state = .authenticating
        lastErrorMessage = nil
        do {
            _ = try await registrationService.registerIfNeeded()
            await login()
        } catch {
            lastErrorMessage = Self.friendlyMessage(for: error)
            state = .needsRegistration
            Log.auth.error("Registration failed: \(String(describing: error), privacy: .public)")
        }
    }

    func login() async {
        guard let identity = await deviceSecretStore.identity() else {
            state = .needsRegistration
            return
        }
        state = .authenticating
        lastErrorMessage = nil
        do {
            let response = try await apiClient.login(
                LoginRequest(deviceId: identity.deviceId, deviceSecret: identity.deviceSecret)
            )
            try await tokenStore.save(TokenPair(response: response, now: dateProvider.now()))
            state = .authenticated(deviceId: identity.deviceId)
            Log.auth.info("Login succeeded")
        } catch {
            lastErrorMessage = Self.friendlyMessage(for: error)
            state = .registered
            Log.auth.error("Login failed: \(String(describing: error), privacy: .public)")
        }
    }

    /// Clears the session but keeps the device identity so the device can
    /// reconnect without re-registering. Stateless JWTs: revocation happens
    /// server-side via credential revocation, not a token blacklist.
    func logout() async {
        try? await tokenStore.clear()
        state = .registered
        lastErrorMessage = nil
        Log.auth.info("Logged out; tokens cleared")
    }

    /// Support/dev escape hatch — forget this device completely.
    func resetDeviceIdentity() async {
        try? await tokenStore.clear()
        try? await deviceSecretStore.clear()
        state = .needsRegistration
        lastErrorMessage = nil
        Log.auth.warning("Device identity reset")
    }

    /// Called by feature code when an authenticated call fails with
    /// `.unauthorized` after refresh — the session is unrecoverable.
    func sessionExpired() {
        state = .registered
        lastErrorMessage = "Session expired — please reconnect."
    }

    private static func friendlyMessage(for error: Error) -> String {
        (error as? APIError)?.userMessage ?? "Something went wrong. Please try again."
    }
}
