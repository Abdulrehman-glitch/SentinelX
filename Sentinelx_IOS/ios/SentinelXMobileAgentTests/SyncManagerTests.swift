import XCTest
@testable import SentinelXMobileAgent

final class SyncManagerTests: XCTestCase {
    private let identity = DeviceIdentity(deviceId: "dev_TEST0001", deviceSecret: "secret")

    private struct World {
        let sync: SyncManager
        let telemetry: TelemetryManager
        let stream: MockTelemetryStream
        let uploader: MockTelemetryUploader
    }

    private func makeWorld(
        flushInterval: TimeInterval = 10,
        batchSize: Int = 100
    ) async throws -> World {
        let keychain = InMemoryKeychain()
        let secretStore = DeviceSecretStore(keychain: keychain)
        try await secretStore.save(identity)

        let apiClient = APIClient(
            environment: TestFixtures.environment(),
            transport: MockHTTPTransport(),
            tokenStore: TokenStore(keychain: keychain),
            deviceSecretStore: secretStore
        )
        let telemetry = TelemetryManager(
            registry: CollectorRegistry(collectors: []),
            configurationService: ConfigurationService(apiClient: apiClient),
            deviceSecretStore: secretStore,
            environment: TestFixtures.environment()
        )
        let stream = MockTelemetryStream()
        let uploader = MockTelemetryUploader()
        let sync = SyncManager(
            telemetryManager: telemetry,
            stream: stream,
            uploader: uploader,
            deviceSecretStore: secretStore,
            flushInterval: flushInterval,
            batchSize: batchSize
        )
        await telemetry.start()
        await sync.start()
        return World(sync: sync, telemetry: telemetry, stream: stream, uploader: uploader)
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

    private func emit(_ count: Int, into telemetry: TelemetryManager) async {
        for _ in 0..<count {
            await telemetry.emit(TelemetryEvent(
                eventId: UUID(),
                deviceId: identity.deviceId,
                timestamp: Date(),
                category: .battery,
                type: "battery.snapshot",
                source: "test.fixture",
                sequence: nil,
                payload: .object(["level": .number(84)]),
                metadata: nil
            ))
        }
    }

    func testEventsFlowOverTheStream() async throws {
        let world = try await makeWorld()

        await emit(2, into: world.telemetry)
        try await waitUntil { world.stream.events.count == 2 }

        let stats = await world.sync.stats
        XCTAssertEqual(stats.sentViaStream, 2)
        XCTAssertEqual(stats.pendingCount, 0)
        XCTAssertTrue(world.uploader.requests.isEmpty)

        await world.sync.stop()
    }

    func testStreamFailureFallsBackToRESTBatch() async throws {
        let world = try await makeWorld(flushInterval: 0.05)
        world.stream.error = WebSocketError.notConnected

        await emit(3, into: world.telemetry)
        try await waitUntil { !world.uploader.requests.isEmpty }
        try await waitUntil { await world.sync.stats.pendingCount == 0 }

        let request = try XCTUnwrap(world.uploader.requests.first)
        XCTAssertEqual(request.deviceId, identity.deviceId)
        XCTAssertEqual(request.events.count, 3)
        let stats = await world.sync.stats
        XCTAssertEqual(stats.sentViaBatch, 3)
        XCTAssertEqual(stats.sentViaStream, 0)

        await world.sync.stop()
    }

    func testReachingBatchSizeFlushesWithoutWaitingForTimer() async throws {
        // Long flush interval — only the size threshold can trigger upload.
        let world = try await makeWorld(flushInterval: 60, batchSize: 2)
        world.stream.error = WebSocketError.notConnected

        await emit(2, into: world.telemetry)
        try await waitUntil { !world.uploader.requests.isEmpty }

        XCTAssertEqual(world.uploader.requests.first?.events.count, 2)

        await world.sync.stop()
    }

    func testUploadFailureKeepsEventsPendingForRetry() async throws {
        let world = try await makeWorld(flushInterval: 60)
        world.stream.error = WebSocketError.notConnected
        world.uploader.error = APIError.networkUnavailable

        await emit(3, into: world.telemetry)
        try await waitUntil { await world.sync.stats.pendingCount == 3 }

        await world.sync.flushPending()
        var stats = await world.sync.stats
        XCTAssertEqual(stats.pendingCount, 3)
        XCTAssertEqual(stats.sentViaBatch, 0)

        // Transport recovers — the same events drain on the next flush.
        world.uploader.error = nil
        await world.sync.flushPending()
        stats = await world.sync.stats
        XCTAssertEqual(stats.pendingCount, 0)
        XCTAssertEqual(stats.sentViaBatch, 3)

        await world.sync.stop()
    }

    func testBatchEncodingOmitsDeviceIdPerContract() throws {
        // Spec 03 §14: batch items carry no device_id (the envelope does).
        let event = TelemetryEvent(
            eventId: UUID(),
            deviceId: identity.deviceId,
            timestamp: Date(),
            category: .battery,
            type: "battery.snapshot",
            source: "test.fixture",
            sequence: 7,
            payload: .object(["level": .number(84)]),
            metadata: nil
        )
        let request = TelemetryBatchRequest(
            deviceId: identity.deviceId,
            batchId: UUID(),
            sentAt: Date(),
            events: [event]
        )

        let data = try JSONCoding.encoder.encode(request)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(json["device_id"] as? String, identity.deviceId)
        let items = try XCTUnwrap(json["events"] as? [[String: Any]])
        XCTAssertNil(items[0]["device_id"])
        XCTAssertEqual(items[0]["sequence"] as? Int, 7)
        XCTAssertNotNil(items[0]["event_id"])
    }
}
