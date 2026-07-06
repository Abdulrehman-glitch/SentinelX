import Foundation

/// REST gateway for the mobile API. Owns JWT attachment, transparent token
/// refresh (single-flight), and mapping of the standard error envelope to
/// typed APIError values. All remote calls in the app go through here or
/// WebSocketClient — never through raw URLSession.
actor APIClient {
    private let environment: AppEnvironment
    private let transport: HTTPTransporting
    private let tokenStore: TokenStore
    private let deviceSecretStore: DeviceSecretStore
    private let dateProvider: DateProviding
    private let uuidProvider: UUIDProviding

    private var refreshTask: Task<TokenPair, Error>?

    init(
        environment: AppEnvironment,
        transport: HTTPTransporting,
        tokenStore: TokenStore,
        deviceSecretStore: DeviceSecretStore,
        dateProvider: DateProviding = SystemDateProvider(),
        uuidProvider: UUIDProviding = SystemUUIDProvider()
    ) {
        self.environment = environment
        self.transport = transport
        self.tokenStore = tokenStore
        self.deviceSecretStore = deviceSecretStore
        self.dateProvider = dateProvider
        self.uuidProvider = uuidProvider
    }

    // MARK: - Contract endpoints

    func register(_ request: DeviceRegistrationRequest) async throws -> DeviceRegistrationResponse {
        try await send(.register, body: request)
    }

    func login(_ request: LoginRequest) async throws -> TokenResponse {
        try await send(.login, body: request)
    }

    func fetchProfile() async throws -> DeviceProfile {
        try await send(.profile)
    }

    func updateProfile(_ request: ProfileUpdateRequest) async throws -> ProfileUpdateResponse {
        try await send(.updateProfile, body: request)
    }

    func fetchConfig() async throws -> AgentConfig {
        try await send(.config)
    }

    // MARK: - Request pipeline

    private func send<Response: Decodable>(_ endpoint: APIEndpoint) async throws -> Response {
        try await perform(endpoint, bodyData: nil, isRetry: false)
    }

    private func send<Body: Encodable, Response: Decodable>(
        _ endpoint: APIEndpoint,
        body: Body
    ) async throws -> Response {
        let data = try JSONCoding.encoder.encode(body)
        return try await perform(endpoint, bodyData: data, isRetry: false)
    }

    private func perform<Response: Decodable>(
        _ endpoint: APIEndpoint,
        bodyData: Data?,
        isRetry: Bool
    ) async throws -> Response {
        var request = await makeRequest(for: endpoint)
        request.httpBody = bodyData

        if endpoint.requiresAuth {
            let token = try await validAccessToken()
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let (data, response) = try await transport.execute(request)

        switch response.statusCode {
        case 200..<300:
            do {
                return try JSONCoding.decoder.decode(Response.self, from: data)
            } catch {
                Log.network.error("Decoding failed for \(endpoint.path, privacy: .public): \(String(describing: error), privacy: .public)")
                throw APIError.decodingFailed
            }
        case 401 where endpoint.requiresAuth && !isRetry:
            // Access token rejected — refresh once and replay the request.
            _ = try await refreshTokens()
            return try await perform(endpoint, bodyData: bodyData, isRetry: true)
        default:
            throw Self.mapError(statusCode: response.statusCode, data: data, response: response)
        }
    }

    private func makeRequest(for endpoint: APIEndpoint) async -> URLRequest {
        var request = URLRequest(url: environment.apiBaseURL.appending(path: endpoint.path))
        request.httpMethod = endpoint.method.rawValue
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("ios", forHTTPHeaderField: "X-Client-Platform")
        request.setValue(environment.agentVersion, forHTTPHeaderField: "X-Agent-Version")
        request.setValue(uuidProvider.uuid().uuidString, forHTTPHeaderField: "X-Request-ID")
        if let identity = await deviceSecretStore.identity() {
            request.setValue(identity.deviceId, forHTTPHeaderField: "X-Device-ID")
        }
        return request
    }

    // MARK: - Token refresh

    private func validAccessToken() async throws -> String {
        if let token = await tokenStore.validAccessToken() {
            return token
        }
        return try await refreshTokens().accessToken
    }

    /// Single-flight: concurrent callers share one in-progress refresh
    /// instead of racing the rotation of the refresh token.
    private func refreshTokens() async throws -> TokenPair {
        if let refreshTask {
            return try await refreshTask.value
        }
        let task = Task { try await self.performTokenRefresh() }
        refreshTask = task
        defer { refreshTask = nil }
        return try await task.value
    }

    private func performTokenRefresh() async throws -> TokenPair {
        guard let refreshToken = await tokenStore.refreshToken() else {
            throw APIError.unauthorized
        }

        var request = await makeRequest(for: .refreshToken)
        request.httpBody = try JSONCoding.encoder.encode(TokenRefreshRequest(refreshToken: refreshToken))

        let (data, response) = try await transport.execute(request)

        guard (200..<300).contains(response.statusCode) else {
            if response.statusCode == 401 || response.statusCode == 403 {
                // Refresh token is dead — the session cannot be recovered
                // silently. Clear tokens; the UI will route back to login.
                try? await tokenStore.clear()
                Log.auth.warning("Refresh token rejected; session cleared")
                throw APIError.unauthorized
            }
            throw Self.mapError(statusCode: response.statusCode, data: data, response: response)
        }

        let tokenResponse: TokenResponse
        do {
            tokenResponse = try JSONCoding.decoder.decode(TokenResponse.self, from: data)
        } catch {
            throw APIError.decodingFailed
        }
        let pair = TokenPair(response: tokenResponse, now: dateProvider.now())
        try await tokenStore.save(pair)
        Log.auth.info("Access token refreshed")
        return pair
    }

    // MARK: - Error mapping

    private static func mapError(statusCode: Int, data: Data, response: HTTPURLResponse) -> APIError {
        let detail = try? JSONCoding.decoder.decode(APIErrorResponse.self, from: data).error
        switch statusCode {
        case 401:
            return .unauthorized
        case 403:
            return .forbidden
        case 404:
            return .notFound
        case 400, 422:
            return .validation(detail?.message ?? "Invalid request")
        case 429:
            let retryAfter = detail?.details?["retry_after_seconds"]?.intValue
                ?? response.value(forHTTPHeaderField: "Retry-After").flatMap(Int.init)
            return .rateLimited(retryAfterSeconds: retryAfter)
        case 500...:
            return .server(detail?.message ?? "Server error")
        default:
            if let detail {
                return .backend(code: detail.code, message: detail.message)
            }
            return .invalidResponse
        }
    }
}
