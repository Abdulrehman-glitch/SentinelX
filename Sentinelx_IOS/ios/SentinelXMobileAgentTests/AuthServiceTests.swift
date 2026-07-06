import XCTest
@testable import SentinelXMobileAgent

@MainActor
final class AuthServiceTests: XCTestCase {
    private let now = Date(timeIntervalSince1970: 1_800_000_000)

    private struct World {
        let auth: AuthService
        let transport: MockHTTPTransport
        let tokenStore: TokenStore
        let secretStore: DeviceSecretStore
    }

    private func makeWorld() -> World {
        let keychain = InMemoryKeychain()
        let transport = MockHTTPTransport()
        let tokenStore = TokenStore(keychain: keychain, dateProvider: FixedDateProvider(fixed: now))
        let secretStore = DeviceSecretStore(keychain: keychain)
        let environment = TestFixtures.environment()
        let client = APIClient(
            environment: environment,
            transport: transport,
            tokenStore: tokenStore,
            deviceSecretStore: secretStore,
            dateProvider: FixedDateProvider(fixed: now)
        )
        let registration = DeviceRegistrationService(
            apiClient: client,
            deviceSecretStore: secretStore,
            deviceInfoProvider: FixedDeviceInfoProvider(),
            environment: environment
        )
        let auth = AuthService(
            apiClient: client,
            tokenStore: tokenStore,
            deviceSecretStore: secretStore,
            registrationService: registration,
            dateProvider: FixedDateProvider(fixed: now)
        )
        return World(auth: auth, transport: transport, tokenStore: tokenStore, secretStore: secretStore)
    }

    func testBootstrapWithEmptyKeychainNeedsRegistration() async {
        let world = makeWorld()
        await world.auth.bootstrapIfNeeded()
        XCTAssertEqual(world.auth.state, .needsRegistration)
    }

    func testRegisterAndLoginHappyPath() async throws {
        let world = makeWorld()
        world.transport.enqueue(.init(statusCode: 201, json: TestFixtures.registrationResponseJSON))
        world.transport.enqueue(.init(statusCode: 200, json: TestFixtures.tokenResponseJSON))

        await world.auth.registerAndLogin()

        XCTAssertEqual(world.auth.state, .authenticated(deviceId: "dev_TEST0001"))
        XCTAssertNil(world.auth.lastErrorMessage)

        // Identity and tokens must be persisted in the (mock) keychain.
        let identity = await world.secretStore.identity()
        XCTAssertEqual(identity, DeviceIdentity(deviceId: "dev_TEST0001", deviceSecret: "test-secret-value"))
        let tokens = await world.tokenStore.currentTokens()
        XCTAssertEqual(tokens?.accessToken, "test-access-token")
    }

    func testLoginFailureLandsInRegisteredStateWithMessage() async throws {
        let world = makeWorld()
        try await world.secretStore.save(DeviceIdentity(deviceId: "dev_TEST0001", deviceSecret: "wrong"))
        world.transport.enqueue(.init(statusCode: 401, json: #"{"error":{"code":"INVALID_TOKEN","message":"bad secret"}}"#))

        await world.auth.login()

        XCTAssertEqual(world.auth.state, .registered)
        XCTAssertNotNil(world.auth.lastErrorMessage)
    }

    func testBootstrapWithTokensGoesStraightToAuthenticated() async throws {
        let world = makeWorld()
        try await world.secretStore.save(DeviceIdentity(deviceId: "dev_TEST0001", deviceSecret: "s"))
        try await world.tokenStore.save(
            TokenPair(accessToken: "a", refreshToken: "r", expiresAt: now.addingTimeInterval(1800))
        )

        await world.auth.bootstrapIfNeeded()

        XCTAssertEqual(world.auth.state, .authenticated(deviceId: "dev_TEST0001"))
        XCTAssertTrue(world.transport.requests.isEmpty, "No network calls needed on warm start")
    }

    func testLogoutClearsTokensKeepsIdentity() async throws {
        let world = makeWorld()
        try await world.secretStore.save(DeviceIdentity(deviceId: "dev_TEST0001", deviceSecret: "s"))
        try await world.tokenStore.save(
            TokenPair(accessToken: "a", refreshToken: "r", expiresAt: now.addingTimeInterval(1800))
        )

        await world.auth.logout()

        XCTAssertEqual(world.auth.state, .registered)
        let tokens = await world.tokenStore.currentTokens()
        XCTAssertNil(tokens)
        let identity = await world.secretStore.identity()
        XCTAssertNotNil(identity)
    }

    func testResetDeviceIdentityClearsEverything() async throws {
        let world = makeWorld()
        try await world.secretStore.save(DeviceIdentity(deviceId: "dev_TEST0001", deviceSecret: "s"))
        try await world.tokenStore.save(
            TokenPair(accessToken: "a", refreshToken: "r", expiresAt: now.addingTimeInterval(1800))
        )

        await world.auth.resetDeviceIdentity()

        XCTAssertEqual(world.auth.state, .needsRegistration)
        let identity = await world.secretStore.identity()
        XCTAssertNil(identity)
        let tokens = await world.tokenStore.currentTokens()
        XCTAssertNil(tokens)
    }
}
