import Foundation

/// Anything that can push a telemetry event upstream in real time.
/// WebSocketClient is the live implementation; SyncManager depends on this
/// protocol so tests can script stream failures.
protocol TelemetryStreaming: Sendable {
    func send(_ event: TelemetryEvent) async throws
}

/// Supplies a valid JWT for the WS handshake (APIClient conforms — it owns
/// refresh).
protocol AccessTokenProviding: Sendable {
    func currentAccessToken() async throws -> String
}

/// Live telemetry channel (docs/spec/03 §16–19): connects to
/// ws/{device_id}, authenticates with a first message, heartbeats every
/// 30s, and reconnects forever with jittered exponential backoff. Server
/// pushes (alert.created, config.update) fan out via `serverMessages()`.
actor WebSocketClient: TelemetryStreaming {
    enum State: Equatable, Sendable {
        case idle, connecting, authenticated, backingOff
    }

    private let environment: AppEnvironment
    private let deviceSecretStore: DeviceSecretStore
    private let tokenProvider: AccessTokenProviding
    private let factory: WebSocketConnectionFactory
    private let reconnectPolicy: RetryPolicy
    private let heartbeatInterval: TimeInterval
    private let dateProvider: DateProviding

    private(set) var state: State = .idle
    private var connection: WebSocketConnecting?
    private var runTask: Task<Void, Never>?
    private var heartbeatTask: Task<Void, Never>?
    private var authenticatedThisConnection = false
    private var rng = SystemRandomNumberGenerator()
    private var subscribers: [UUID: AsyncStream<WSServerMessage>.Continuation] = [:]

    init(
        environment: AppEnvironment,
        deviceSecretStore: DeviceSecretStore,
        tokenProvider: AccessTokenProviding,
        factory: WebSocketConnectionFactory = URLSessionWebSocketConnectionFactory(),
        reconnectPolicy: RetryPolicy = .reconnect,
        heartbeatInterval: TimeInterval = AppConstants.heartbeatIntervalSeconds,
        dateProvider: DateProviding = SystemDateProvider()
    ) {
        self.environment = environment
        self.deviceSecretStore = deviceSecretStore
        self.tokenProvider = tokenProvider
        self.factory = factory
        self.reconnectPolicy = reconnectPolicy
        self.heartbeatInterval = heartbeatInterval
        self.dateProvider = dateProvider
    }

    var isConnected: Bool { state == .authenticated }

    func start() {
        guard runTask == nil else { return }
        runTask = Task { await runLoop() }
    }

    func stop() {
        runTask?.cancel()
        runTask = nil
        teardownConnection()
        state = .idle
    }

    // MARK: - TelemetryStreaming

    func send(_ event: TelemetryEvent) async throws {
        guard state == .authenticated, let connection else {
            throw WebSocketError.notConnected
        }
        try await connection.send(text: Self.encode(WSClientMessage.TelemetryEventMessage(event: event)))
    }

    /// Live feed of server-initiated messages (alerts, config updates).
    func serverMessages() -> AsyncStream<WSServerMessage> {
        AsyncStream { continuation in
            let id = UUID()
            subscribers[id] = continuation
            continuation.onTermination = { _ in
                Task { await self.removeSubscriber(id) }
            }
        }
    }

    // MARK: - Connection lifecycle

    private func runLoop() async {
        var attempt = 1
        while !Task.isCancelled {
            authenticatedThisConnection = false
            do {
                try await connectAndServe()
            } catch is CancellationError {
                break
            } catch {
                Log.network.warning("WS connection ended: \(String(describing: error), privacy: .public)")
            }
            teardownConnection()
            if authenticatedThisConnection {
                attempt = 1
            }
            if Task.isCancelled { break }

            state = .backingOff
            guard let delay = reconnectPolicy.jitteredDelay(forAttempt: attempt, using: &rng) else {
                Log.network.error("WS reconnect attempts exhausted")
                break
            }
            attempt += 1
            try? await Task.sleep(for: .seconds(delay))
        }
        state = .idle
    }

    private func connectAndServe() async throws {
        guard let identity = await deviceSecretStore.identity() else {
            throw WebSocketError.notConnected // not registered yet; retry later
        }
        let token = try await tokenProvider.currentAccessToken()

        state = .connecting
        let connection = factory.open(url: environment.webSocketBaseURL.appending(path: identity.deviceId))
        self.connection = connection

        try await connection.send(text: Self.encode(
            WSClientMessage.Auth(accessToken: token, deviceId: identity.deviceId)
        ))
        let reply = try Self.decode(await connection.receiveText())
        guard case .authAccepted = reply else {
            if case .authRejected(let reason) = reply {
                throw WebSocketError.authRejected(reason: reason)
            }
            throw WebSocketError.unexpectedMessage
        }

        state = .authenticated
        authenticatedThisConnection = true
        Log.network.info("WS authenticated")
        startHeartbeat(deviceId: identity.deviceId, over: connection)

        while !Task.isCancelled {
            let message = try Self.decode(await connection.receiveText())
            handle(message)
        }
    }

    private func startHeartbeat(deviceId: String, over connection: WebSocketConnecting) {
        heartbeatTask?.cancel()
        let interval = heartbeatInterval
        let dateProvider = self.dateProvider
        heartbeatTask = Task {
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(interval))
                guard !Task.isCancelled else { break }
                let beat = WSClientMessage.Heartbeat(deviceId: deviceId, timestamp: dateProvider.now())
                guard let text = try? Self.encode(beat), (try? await connection.send(text: text)) != nil else {
                    break // send failure — receive loop will fail too and reconnect
                }
            }
        }
    }

    private func handle(_ message: WSServerMessage) {
        switch message {
        case .serverError(let code, let errorMessage):
            Log.network.warning("WS server error \(code, privacy: .public): \(errorMessage, privacy: .public)")
        case .heartbeatAck, .authAccepted, .authRejected, .alertCreated, .unhandled:
            break
        }
        for continuation in subscribers.values {
            continuation.yield(message)
        }
    }

    private func teardownConnection() {
        heartbeatTask?.cancel()
        heartbeatTask = nil
        connection?.close()
        connection = nil
    }

    private func removeSubscriber(_ id: UUID) {
        subscribers.removeValue(forKey: id)
    }

    // MARK: - Coding

    private static func encode(_ message: some Encodable) throws -> String {
        let data = try JSONCoding.encoder.encode(message)
        guard let text = String(data: data, encoding: .utf8) else {
            throw WebSocketError.unexpectedMessage
        }
        return text
    }

    private static func decode(_ text: String) throws -> WSServerMessage {
        guard let data = text.data(using: .utf8) else {
            throw WebSocketError.unexpectedMessage
        }
        return try JSONCoding.decoder.decode(WSServerMessage.self, from: data)
    }
}
