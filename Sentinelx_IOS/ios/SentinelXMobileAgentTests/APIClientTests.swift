import XCTest
@testable import SentinelXMobileAgent

final class APIClientTests: XCTestCase {
    private let now = Date(timeIntervalSince1970: 1_800_000_000)

    private struct World {
        let client: APIClient
        let transport: MockHTTPTransport
        let tokenStore: TokenStore
        let secretStore: DeviceSecretStore
        let keychain: InMemoryKeychain
    }

    private func makeWorld() -> World {
        let keychain = InMemoryKeychain()
        let transport = MockHTTPTransport()
        let tokenStore = TokenStore(keychain: keychain, dateProvider: FixedDateProvider(fixed: now))
        let secretStore = DeviceSecretStore(keychain: keychain)
        let client = APIClient(
            environment: TestFixtures.environment(),
            transport: transport,
            tokenStore: tokenStore,
            deviceSecretStore: secretStore,
            dateProvider: FixedDateProvider(fixed: now)
        )
        return World(client: client, transport: transport, tokenStore: tokenStore, secretStore: secretStore, keychain: keychain)
    }

    private func validPair(access: String = "valid-access") -> TokenPair {
        TokenPair(accessToken: access, refreshToken: "valid-refresh", expiresAt: now.addingTimeInterval(1800))
    }

    func testRegisterSendsUnauthenticatedPostAndDecodes() async throws {
        let world = makeWorld()
        world.transport.enqueue(.init(statusCode: 201, json: TestFixtures.registrationResponseJSON))

        let request = DeviceRegistrationRequest(
            platform: .ios, deviceName: "n", deviceModel: "m", osVersion: "o",
            appVersion: "1", vendorIdentifier: "v", timezone: "tz", locale: "lc"
        )
        let response = try await world.client.register(request)

        XCTAssertEqual(response.deviceId, "dev_TEST0001")
        let sent = try XCTUnwrap(world.transport.requests.first)
        XCTAssertEqual(sent.httpMethod, "POST")
        XCTAssertEqual(sent.url?.path, "/api/v1/mobile/register")
        XCTAssertNil(sent.value(forHTTPHeaderField: "Authorization"))
        XCTAssertEqual(sent.value(forHTTPHeaderField: "X-Client-Platform"), "ios")
        XCTAssertNotNil(sent.value(forHTTPHeaderField: "X-Request-ID"))
    }

    func testAuthenticatedRequestAttachesBearerToken() async throws {
        let world = makeWorld()
        try await world.tokenStore.save(validPair())
        world.transport.enqueue(.init(statusCode: 200, json: TestFixtures.profileJSON))

        _ = try await world.client.fetchProfile()

        let sent = try XCTUnwrap(world.transport.requests.first)
        XCTAssertEqual(sent.value(forHTTPHeaderField: "Authorization"), "Bearer valid-access")
    }

    func testExpiredTokenTriggersRefreshBeforeRequest() async throws {
        let world = makeWorld()
        // Expired access token, live refresh token.
        try await world.tokenStore.save(
            TokenPair(accessToken: "stale", refreshToken: "valid-refresh", expiresAt: now.addingTimeInterval(-10))
        )
        world.transport.enqueue(.init(statusCode: 200, json: TestFixtures.refreshedTokenResponseJSON))
        world.transport.enqueue(.init(statusCode: 200, json: TestFixtures.profileJSON))

        _ = try await world.client.fetchProfile()

        XCTAssertEqual(world.transport.recordedPaths, [
            "/api/v1/mobile/token/refresh",
            "/api/v1/mobile/profile",
        ])
        let profileRequest = world.transport.requests[1]
        XCTAssertEqual(profileRequest.value(forHTTPHeaderField: "Authorization"), "Bearer refreshed-access-token")
        // Rotated pair must be persisted.
        let stored = await world.tokenStore.currentTokens()
        XCTAssertEqual(stored?.refreshToken, "refreshed-refresh-token")
    }

    func testServer401RefreshesAndRetriesOnce() async throws {
        let world = makeWorld()
        try await world.tokenStore.save(validPair())
        world.transport.enqueue(.init(statusCode: 401, json: #"{"error":{"code":"INVALID_TOKEN","message":"expired"}}"#))
        world.transport.enqueue(.init(statusCode: 200, json: TestFixtures.refreshedTokenResponseJSON))
        world.transport.enqueue(.init(statusCode: 200, json: TestFixtures.profileJSON))

        let profile = try await world.client.fetchProfile()

        XCTAssertEqual(profile.deviceId, "dev_TEST0001")
        XCTAssertEqual(world.transport.recordedPaths, [
            "/api/v1/mobile/profile",
            "/api/v1/mobile/token/refresh",
            "/api/v1/mobile/profile",
        ])
    }

    func testRefreshRejectionClearsSessionAndThrowsUnauthorized() async throws {
        let world = makeWorld()
        try await world.tokenStore.save(
            TokenPair(accessToken: "stale", refreshToken: "dead-refresh", expiresAt: now.addingTimeInterval(-10))
        )
        world.transport.enqueue(.init(statusCode: 401, json: #"{"error":{"code":"INVALID_TOKEN","message":"revoked"}}"#))

        do {
            _ = try await world.client.fetchProfile()
            XCTFail("Expected APIError.unauthorized")
        } catch let error as APIError {
            XCTAssertEqual(error, .unauthorized)
        }
        let tokens = await world.tokenStore.currentTokens()
        XCTAssertNil(tokens)
    }

    func testRateLimitMapsRetryAfterFromDetails() async throws {
        let world = makeWorld()
        try await world.tokenStore.save(validPair())
        world.transport.enqueue(.init(
            statusCode: 429,
            json: #"{"error":{"code":"RATE_LIMITED","message":"Too many","details":{"retry_after_seconds":30}}}"#
        ))

        do {
            _ = try await world.client.fetchProfile()
            XCTFail("Expected APIError.rateLimited")
        } catch let error as APIError {
            XCTAssertEqual(error, .rateLimited(retryAfterSeconds: 30))
        }
    }

    func testValidationErrorCarriesServerMessage() async throws {
        let world = makeWorld()
        world.transport.enqueue(.init(
            statusCode: 422,
            json: #"{"error":{"code":"VALIDATION_ERROR","message":"platform must be one of ios, android"}}"#
        ))

        do {
            _ = try await world.client.register(DeviceRegistrationRequest(
                platform: .unknown, deviceName: "n", deviceModel: "m", osVersion: "o",
                appVersion: "1", vendorIdentifier: "v", timezone: "tz", locale: "lc"
            ))
            XCTFail("Expected APIError.validation")
        } catch let error as APIError {
            XCTAssertEqual(error, .validation("platform must be one of ios, android"))
        }
    }
}
