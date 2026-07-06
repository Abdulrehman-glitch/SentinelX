import XCTest
@testable import SentinelXMobileAgent

final class WebSocketClientTests: XCTestCase {
    private let identity = DeviceIdentity(deviceId: "dev_TEST0001", deviceSecret: "secret")

    private struct World {
        let client: WebSocketClient
        let factory: MockWebSocketConnectionFactory
        let secretStore: DeviceSecretStore
    }

    private func makeWorld(
        connections: [MockWebSocketConnection],
        reconnectPolicy: RetryPolicy = RetryPolicy(baseDelay: 0.01, multiplier: 1, maxDelay: 0.01, maxAttempts: nil),
        heartbeatInterval: TimeInterval = 60
    ) async throws -> World {
        let secretStore = DeviceSecretStore(keychain: InMemoryKeychain())
        try await secretStore.save(identity)
        let factory = MockWebSocketConnectionFactory(connections: connections)
        let client = WebSocketClient(
            environment: TestFixtures.environment(),
            deviceSecretStore: secretStore,
            tokenProvider: MockAccessTokenProvider(),
            factory: factory,
            reconnectPolicy: reconnectPolicy,
            heartbeatInterval: heartbeatInterval
        )
        return World(client: client, factory: factory, secretStore: secretStore)
    }

    private func waitUntil(
        timeout: TimeInterval = 2,
        _ condition: @escaping () async -> Bool
    ) async throws {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if await condition() { return }
            try await Task.sleep(for: .milliseconds(10))
        }
        XCTFail("Condition not met within \(timeout)s")
    }

    private static let authAccepted = """
    {"type": "auth.accepted", "device_id": "dev_TEST0001", "server_time": "2026-07-06T12:00:00Z"}
    """

    func testHandshakeSendsFirstMessageAuthAndConnects() async throws {
        let connection = MockWebSocketConnection()
        connection.push(Self.authAccepted)
        let world = try await makeWorld(connections: [connection])

        await world.client.start()
        try await waitUntil { await world.client.isConnected }

        XCTAssertEqual(world.factory.openedURLs.first?.lastPathComponent, "dev_TEST0001")
        let first = try XCTUnwrap(connection.sentTexts.first)
        XCTAssertTrue(first.contains("\"type\":\"auth\""))
        XCTAssertTrue(first.contains("test-access-token"))
        XCTAssertTrue(first.contains("dev_TEST0001"))

        await world.client.stop()
    }

    func testAuthRejectionTriggersReconnectOnFreshConnection() async throws {
        let rejecting = MockWebSocketConnection()
        rejecting.push("""
        {"type": "auth.rejected", "reason": "INVALID_TOKEN"}
        """)
        let accepting = MockWebSocketConnection()
        accepting.push(Self.authAccepted)
        let world = try await makeWorld(connections: [rejecting, accepting])

        await world.client.start()
        try await waitUntil { await world.client.isConnected }

        XCTAssertEqual(world.factory.openedURLs.count, 2)
        await world.client.stop()
    }

    func testDroppedConnectionReconnects() async throws {
        let first = MockWebSocketConnection()
        first.push(Self.authAccepted)
        let second = MockWebSocketConnection()
        second.push(Self.authAccepted)
        let world = try await makeWorld(connections: [first, second])

        await world.client.start()
        try await waitUntil { await world.client.isConnected }

        first.dropConnection()
        try await waitUntil { world.factory.openedURLs.count == 2 }
        try await waitUntil { await world.client.isConnected }

        await world.client.stop()
    }

    func testSendWhileDisconnectedThrowsNotConnected() async throws {
        let world = try await makeWorld(connections: [MockWebSocketConnection()])

        do {
            try await world.client.send(makeEvent())
            XCTFail("Expected notConnected")
        } catch let error as WebSocketError {
            XCTAssertEqual(error, .notConnected)
        }
    }

    func testSendDeliversTelemetryEnvelope() async throws {
        let connection = MockWebSocketConnection()
        connection.push(Self.authAccepted)
        let world = try await makeWorld(connections: [connection])

        await world.client.start()
        try await waitUntil { await world.client.isConnected }

        let event = makeEvent()
        try await world.client.send(event)

        let frame = try XCTUnwrap(connection.sentTexts.last)
        XCTAssertTrue(frame.contains("\"type\":\"telemetry.event\""))
        XCTAssertTrue(frame.contains(event.eventId.uuidString.lowercased())
            || frame.contains(event.eventId.uuidString))

        await world.client.stop()
    }

    func testHeartbeatIsSentOnInterval() async throws {
        let connection = MockWebSocketConnection()
        connection.push(Self.authAccepted)
        let world = try await makeWorld(connections: [connection], heartbeatInterval: 0.05)

        await world.client.start()
        try await waitUntil { await world.client.isConnected }
        try await waitUntil {
            connection.sentTexts.contains { $0.contains("\"type\":\"heartbeat\"") }
        }

        await world.client.stop()
    }

    private func makeEvent() -> TelemetryEvent {
        TelemetryEvent(
            eventId: UUID(),
            deviceId: identity.deviceId,
            timestamp: Date(),
            category: .battery,
            type: "battery.snapshot",
            source: "test.fixture",
            sequence: 1,
            payload: .object(["level": .number(84)]),
            metadata: nil
        )
    }
}
