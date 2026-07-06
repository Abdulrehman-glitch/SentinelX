import XCTest
@testable import SentinelXMobileAgent

final class TelemetryQueueTests: XCTestCase {
    private var dbPath: String!

    override func setUp() {
        super.setUp()
        dbPath = FileManager.default.temporaryDirectory
            .appendingPathComponent("queue-\(UUID().uuidString).db").path
    }

    override func tearDown() {
        for suffix in ["", "-wal", "-shm"] {
            try? FileManager.default.removeItem(atPath: dbPath + suffix)
        }
        super.tearDown()
    }

    private func makeQueue() throws -> TelemetryQueue {
        try TelemetryQueue(path: dbPath)
    }

    private func makeEvent(sequence: Int = 1) -> TelemetryEvent {
        TelemetryEvent(
            eventId: UUID(),
            deviceId: "dev_TEST0001",
            // Whole seconds: the wire format is millisecond-precision, so a
            // sub-ms Date would not roundtrip Equatable.
            timestamp: Date(timeIntervalSince1970: 1_800_000_000),
            category: .battery,
            type: "battery.snapshot",
            source: "test.fixture",
            sequence: sequence,
            payload: .object(["level": .number(84), "charging": .bool(false)]),
            metadata: TelemetryMetadata(
                platform: .ios, agentVersion: "1.0.0",
                collectorVersion: nil, appBuild: nil, environment: "test"
            )
        )
    }

    func testEnqueueAndFIFOBatchRoundtrip() async throws {
        let queue = try makeQueue()
        let first = makeEvent(sequence: 1)
        let second = makeEvent(sequence: 2)
        try await queue.enqueue(first)
        try await queue.enqueue(second)

        let batch = try await queue.nextBatch(limit: 10)
        XCTAssertEqual(batch.map(\.eventId), [first.eventId, second.eventId])
        // Full envelope survives the roundtrip.
        XCTAssertEqual(batch[0], first)

        // Batch is now in_flight — not eligible again.
        let again = try await queue.nextBatch(limit: 10)
        XCTAssertTrue(again.isEmpty)
        let counts = try await queue.counts()
        XCTAssertEqual(counts.inFlight, 2)
        XCTAssertEqual(counts.pending, 0)
    }

    func testDuplicateEventIdIsIgnored() async throws {
        let queue = try makeQueue()
        let event = makeEvent()
        let firstInsert = try await queue.enqueue(event)
        let secondInsert = try await queue.enqueue(event)
        XCTAssertTrue(firstInsert)
        XCTAssertFalse(secondInsert)
        let counts = try await queue.counts()
        XCTAssertEqual(counts.pending, 1)
    }

    func testMarkUploadedRemovesEvents() async throws {
        let queue = try makeQueue()
        let event = makeEvent()
        try await queue.enqueue(event)
        let batch = try await queue.nextBatch(limit: 1)
        try await queue.markUploaded(batch.map(\.eventId))

        let counts = try await queue.counts()
        XCTAssertEqual(counts, QueueCounts())
    }

    func testRetryReturnsToPendingThenFailsAfterMaxAttempts() async throws {
        let queue = try makeQueue()
        let event = makeEvent()
        try await queue.enqueue(event)

        for attempt in 1...TelemetryQueue.maxAttempts {
            let batch = try await queue.nextBatch(limit: 1)
            if attempt < TelemetryQueue.maxAttempts {
                XCTAssertEqual(batch.count, 1, "attempt \(attempt) should see the event")
            }
            try await queue.markForRetry(batch.map(\.eventId), error: "boom \(attempt)")
        }

        let counts = try await queue.counts()
        XCTAssertEqual(counts.failed, 1)
        XCTAssertEqual(counts.pending, 0)

        try await queue.clearFailed()
        let cleared = try await queue.counts()
        XCTAssertEqual(cleared.failed, 0)
    }

    func testRequeueInFlightRecoversUnacknowledgedSends() async throws {
        let queue = try makeQueue()
        try await queue.enqueue(makeEvent())
        _ = try await queue.nextBatch(limit: 1)
        let before = try await queue.counts()
        XCTAssertEqual(before.inFlight, 1)

        try await queue.requeueInFlight()
        let counts = try await queue.counts()
        XCTAssertEqual(counts.pending, 1)
        XCTAssertEqual(counts.inFlight, 0)
    }

    func testEventsSurviveReopen() async throws {
        // Airplane-mode foundation: enqueue, "kill the app" (drop the queue),
        // reopen the same file, events are still there.
        let event = makeEvent()
        do {
            let queue = try makeQueue()
            try await queue.enqueue(event)
            _ = try await queue.nextBatch(limit: 1) // left in_flight, as a crash would
        }

        let reopened = try makeQueue()
        try await reopened.requeueInFlight()
        let recovered = try await reopened.nextBatch(limit: 10)
        XCTAssertEqual(recovered.map(\.eventId), [event.eventId])
        XCTAssertEqual(recovered[0].payload, event.payload)
    }

    func testPendingPruneCapsQueueDroppingOldest() async throws {
        let queue = try makeQueue()
        var eventIds: [UUID] = []
        for sequence in 0..<(TelemetryQueue.pendingCap + 5) {
            let event = makeEvent(sequence: sequence)
            eventIds.append(event.eventId)
            try await queue.enqueue(event)
        }

        let counts = try await queue.counts()
        XCTAssertEqual(counts.pending, TelemetryQueue.pendingCap)
        let dropped = await queue.droppedByPrune
        XCTAssertEqual(dropped, 5)

        // The oldest five were dropped; the head of the queue is event #5.
        let batch = try await queue.nextBatch(limit: 1)
        XCTAssertEqual(batch.first?.eventId, eventIds[5])
    }
}
