import Foundation

struct TokenPair: Codable, Equatable, Sendable {
    let accessToken: String
    let refreshToken: String
    let expiresAt: Date
}

extension TokenPair {
    init(response: TokenResponse, now: Date) {
        self.init(
            accessToken: response.accessToken,
            refreshToken: response.refreshToken,
            expiresAt: now.addingTimeInterval(TimeInterval(response.expiresIn))
        )
    }
}

/// Keychain-backed storage for the JWT pair. Actor-isolated so concurrent
/// API calls see a consistent view during refresh.
actor TokenStore {
    private enum Key {
        static let tokens = "auth.tokens"
    }

    private let keychain: KeychainStoring
    private let dateProvider: DateProviding
    private var cached: TokenPair?
    private var loaded = false

    init(keychain: KeychainStoring, dateProvider: DateProviding = SystemDateProvider()) {
        self.keychain = keychain
        self.dateProvider = dateProvider
    }

    func currentTokens() -> TokenPair? {
        loadIfNeeded()
        return cached
    }

    /// Access token if present and not within the expiry leeway window.
    func validAccessToken(leeway: TimeInterval = AppConstants.tokenExpiryLeewaySeconds) -> String? {
        loadIfNeeded()
        guard let cached else { return nil }
        guard cached.expiresAt.timeIntervalSince(dateProvider.now()) > leeway else { return nil }
        return cached.accessToken
    }

    func refreshToken() -> String? {
        loadIfNeeded()
        return cached?.refreshToken
    }

    func save(_ tokens: TokenPair) throws {
        let data = try JSONCoding.encoder.encode(tokens)
        try keychain.set(data, for: Key.tokens)
        cached = tokens
        loaded = true
    }

    func clear() throws {
        try keychain.removeValue(for: Key.tokens)
        cached = nil
        loaded = true
    }

    private func loadIfNeeded() {
        guard !loaded else { return }
        loaded = true
        guard let data = try? keychain.data(for: Key.tokens) else { return }
        cached = try? JSONCoding.decoder.decode(TokenPair.self, from: data)
    }
}
