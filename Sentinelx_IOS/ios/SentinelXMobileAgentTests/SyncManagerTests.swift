import XCTest
@testable import SentinelXMobileAgent

final class SyncManagerTests: XCTestCase {
    private let identity = DeviceIdentity(deviceId: "dev_TEST0001", deviceSecret: "secret")
    private var dbPath: String!

    override func setUp() {
        super.setUp()
        dbPath = FileManager.default.temporaryDirectory
            .appendingPathComponent("sync-queue-\(UUID().uuidString).db").path
    }

    override func tearDown() {
        for suffix in ["", "-wal", "-shm"] {
            try? FileManager.default.removeItem(atPath: dbPath + suffix)
        }
        super.tearDown()
    }

    private struct World {
        let sync: SyncManager
        let telemetry: TelemetryManager
        let stream: MockTelemetryStream
        let uploader: MockTelemetryUploader
        let queue: TelemetryQueue
    }

    private func makeWorld(
        flushInterval: TimeInterval = 60,
        batchSize: Int = 100,
        connected: Bool = false
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
        let queue = try TelemetryQueue(path: dbPath)
        let sync = SyncManager(
            telemetryManager: telemetry,
            stream: stream,
            uploader: uploader,
            queue: queue,
            deviceSecretStore: secretStore,
            flushInterval: flushInterval,
            batchSize: batchSize
        )
        await telemetry.start()
        await sync.start()
        if connected {
            stream.emitConnection(.connected)
            try await waitUntil { await sync.streamConnected }
        }
        return World(sync: sync, telemetry: telemetry, stream: stream, uploader: uploader, queue: queue)
    }

    private func waitUntil(
        timeout: TimeInterval = 10, // generous: CI simulators schedule tasks slowly
        _ condition: @escaping () async -> Bool
    ) async throws {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if await condition() { return }
            try await Task.sleep(for: .milliseconds(10))
        }
        XCTFail("Condition not met within \(timeout)s")
    }

    @discardableResult
    private func emit(_ count: Int, into telemetry: TelemetryManager) async -> [UUID] {
        var ids: [UUID] = []
        for _ in 0..<count {
            let event = TelemetryEvent(
                eventId: UUID(),
                deviceId: identity.deviceId,
                timestamp: Date(),
                category: .battery,
                type: "battery.snapshot",
                source: "test.fixture",
                sequence: nil,
                payload: .object(["level": .number(84)]),
                metadata: nil
            )
            ids.append(event.eventId)
            await telemetry.emit(event)
        }
        return ids
    }

    private func uploadedEventIds(_ uploader: MockTelemetryUploader) -> [UUID] {
        uploader.requests.flatMap { $0.events.map(\.event.eventId) }
    }

    func testConnectedEventsFlowOverTheStream() async throws {
        let world = try await makeWorld(connected: true)

        await emit(2, into: world.telemetry)
        try await waitUntil { world.stream.events.count == 2 }

        let stats = await world.sync.stats
        XCTAssertEqual(stats.sentViaStream, 2)
        XCTAssertTrue(world.uploader.requests.isEmpty)
        let counts = await world.sync.queueCounts()
        XCTAssertEqual(counts.pending, 0)
        // No WS ack yet (P5.3) — stream sends await it as in_flight.
        XCTAssertEqual(counts.inFlight, 2)

        await world.sync.stop()
    }

    func testStreamFailureFallsBackToRESTBatch() async throws {
        let world = try await makeWorld(connected: true)
        world.stream.error = WebSocketError.notConnected

        let ids = await emit(3, into: world.telemetry)
        try await waitUntil { self.uploadedEventIds(world.uploader).count == 3 }

        XCTAssertEqual(Set(uploadedEventIds(world.uploader)), Set(ids))
        let stats = await world.sync.stats
        XCTAssertEqual(stats.sentViaStream, 0)
        XCTAssertEqual(stats.sentViaBatch, 3)
        try await waitUntil { await world.sync.queueCounts() == QueueCounts() }

        await world.sync.stop()
    }

    func testDisconnectedEventsBatchViaRESTOnFlushTick() async throws {
        let world = try await makeWorld(flushInterval: 0.05)

        let ids = await emit(3, into: world.telemetry)
        try await waitUntil { self.uploadedEventIds(world.uploader).count == 3 }
        try await waitUntil { await world.sync.queueCounts() == QueueCounts() }

        XCTAssertEqual(Set(uploadedEventIds(world.uploader)), Set(ids))
        XCTAssertEqual(world.uploader.requests.first?.deviceId, identity.deviceId)
        let stats = await world.sync.stats
        XCTAssertEqual(stats.sentViaBatch, 3)
        XCTAssertEqual(stats.sentViaStream, 0)

        await world.sync.stop()
    }

    func testReachingBatchSizeFlushesWithoutWaitingForTimer() async throws {
        // Long flush interval — only the size threshold can trigger upload.
        let world = try await makeWorld(flushInterval: 60, batchSize: 2)

        await emit(2, into: world.telemetry)
        try await waitUntil { !world.uploader.requests.isEmpty }

        XCTAssertEqual(world.uploader.requests.first?.events.count, 2)

        await world.sync.stop()
    }

    func testTransportFailureKeepsEventsPendingThenRecovers() async throws {
        let world = try await makeWorld(flushInterval: 60)
        world.uploader.error = APIError.networkUnavailable

        let ids = await emit(3, into: world.telemetry)
        try await waitUntil { await world.sync.queueCounts().pending == 3 }

        await world.sync.flushNow()
        var counts = await world.sync.queueCounts()
        XCTAssertEqual(counts.pending, 3) // marked for retry, still durable
        var stats = await world.sync.stats
        XCTAssertEqual(stats.sentViaBatch, 0)

        // Transport recovers — flushNow bypasses the backoff gate.
        world.uploader.error = nil
        await world.sync.flushNow()
        counts = await world.sync.queueCounts()
        XCTAssertEqual(counts, QueueCounts())
        stats = await world.sync.stats
        XCTAssertEqual(stats.sentViaBatch, 3)
        XCTAssertEqual(Set(uploadedEventIds(world.uploader)), Set(ids))
        XCTAssertEqual(uploadedEventIds(world.uploader).count, 3)

        await world.sync.stop()
    }

    func testServerRejectedEventsAreMarkedFailedAndNotRetried() async throws {
        let world = try await makeWorld(flushInterval: 60)
        let ids = await emit(3, into: world.telemetry)
        try await waitUntil { await world.sync.queueCounts().pending == 3 }
        world.uploader.rejectedIds = [ids[1]]

        await world.sync.flushNow()
        let counts = await world.sync.queueCounts()
        XCTAssertEqual(counts.pending, 0)
        XCTAssertEqual(counts.failed, 1)
        let stats = await world.sync.stats
        XCTAssertEqual(stats.sentViaBatch, 2)
        XCTAssertEqual(stats.rejectedByServer, 1)

        await world.sync.flushNow()
        XCTAssertEqual(world.uploader.requests.count, 1, "failed events must not be retried")

        await world.sync.stop()
    }

    func testDisconnectRequeuesUnacknowledgedStreamSends() async throws {
        let world = try await makeWorld(connected: true)
        let ids = await emit(2, into: world.telemetry)
        try await waitUntil { world.stream.events.count == 2 }
        var counts = await world.sync.queueCounts()
        XCTAssertEqual(counts.inFlight, 2)

        // Socket dies before any ack — everything goes back to pending.
        world.stream.emitConnection(.disconnected)
        try await waitUntil { await world.sync.queueCounts().pending == 2 }

        // Reconnect drains again; the server dedupes by event_id.
        world.stream.emitConnection(.connected)
        try await waitUntil { world.stream.events.count == 4 }
        XCTAssertEqual(Set(world.stream.events.suffix(2).map(\.eventId)), Set(ids))
        counts = await world.sync.queueCounts()
        XCTAssertEqual(counts.pending, 0)
        XCTAssertEqual(counts.inFlight, 2)

        await world.sync.stop()
    }

    func testAirplaneModeEventsSurviveRelaunchAndDrainExactlyOnce() async throws {
        // Both transports down: events must persist, then upload exactly
        // once after a simulated relaunch (new queue instance, same file).
        var sentIds: [UUID] = []
        do {
            let world = try await makeWorld()
            world.uploader.error = APIError.networkUnavailable
            sentIds = await emit(3, into: world.telemetry)
            try await waitUntil { await world.sync.queueCounts().pending == 3 }

            await world.sync.flushNow()
            try await waitUntil { await world.sync.queueCounts().pending == 3 }
            XCTAssertTrue(world.uploader.requests.isEmpty)

            // Crash mid-send: leave the batch in_flight, no clean stop.
            _ = try await world.queue.nextBatch(limit: 10)
        }

        let relaunched = try await makeWorld() // start() requeues in_flight
        await relaunched.sync.flushNow()

        let uploaded = uploadedEventIds(relaunched.uploader)
        XCTAssertEqual(Set(uploaded), Set(sentIds))
        XCTAssertEqual(uploaded.count, 3, "recovery must drain exactly once")
        let counts = await relaunched.sync.queueCounts()
        XCTAssertEqual(counts, QueueCounts())

        await relaunched.sync.stop()
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
