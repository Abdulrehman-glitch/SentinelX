import XCTest
@testable import SentinelXMobileAgent

final class TokenStoreTests: XCTestCase {
    private let now = Date(timeIntervalSince1970: 1_800_000_000)

    func testSaveAndReadBack() async throws {
        let keychain = InMemoryKeychain()
        let store = TokenStore(keychain: keychain, dateProvider: FixedDateProvider(fixed: now))
        let pair = TokenPair(accessToken: "a", refreshToken: "r", expiresAt: now.addingTimeInterval(1800))

        try await store.save(pair)

        let valid = await store.validAccessToken()
        XCTAssertEqual(valid, "a")
        let refresh = await store.refreshToken()
        XCTAssertEqual(refresh, "r")
    }

    func testTokenWithinLeewayIsNotValid() async throws {
        let keychain = InMemoryKeychain()
        let store = TokenStore(keychain: keychain, dateProvider: FixedDateProvider(fixed: now))
        // Expires in 30s — inside the 60s leeway window.
        let pair = TokenPair(accessToken: "a", refreshToken: "r", expiresAt: now.addingTimeInterval(30))

        try await store.save(pair)

        let valid = await store.validAccessToken()
        XCTAssertNil(valid)
        // Refresh token must still be readable so the session can recover.
        let refresh = await store.refreshToken()
        XCTAssertEqual(refresh, "r")
    }

    func testPersistsAcrossInstances() async throws {
        let keychain = InMemoryKeychain()
        let first = TokenStore(keychain: keychain, dateProvider: FixedDateProvider(fixed: now))
        let pair = TokenPair(accessToken: "a", refreshToken: "r", expiresAt: now.addingTimeInterval(1800))
        try await first.save(pair)

        let second = TokenStore(keychain: keychain, dateProvider: FixedDateProvider(fixed: now))
        let tokens = await second.currentTokens()
        XCTAssertEqual(tokens, pair)
    }

    func testClearRemovesTokens() async throws {
        let keychain = InMemoryKeychain()
        let store = TokenStore(keychain: keychain, dateProvider: FixedDateProvider(fixed: now))
        try await store.save(TokenPair(accessToken: "a", refreshToken: "r", expiresAt: now.addingTimeInterval(1800)))

        try await store.clear()

        let tokens = await store.currentTokens()
        XCTAssertNil(tokens)
        let reloaded = await TokenStore(keychain: keychain).currentTokens()
        XCTAssertNil(reloaded)
    }
}
