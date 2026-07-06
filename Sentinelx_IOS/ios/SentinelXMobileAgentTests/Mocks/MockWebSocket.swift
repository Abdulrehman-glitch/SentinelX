import Foundation
@testable import SentinelXMobileAgent

/// Scripted WebSocket: tests push inbound frames and read recorded outbound
/// frames. `receiveText` blocks until a frame is pushed, mirroring a live
/// socket; finishing the stream simulates a disconnect.
final class MockWebSocketConnection: WebSocketConnecting, @unchecked Sendable {
    private let lock = NSLock()
    private var sent: [String] = []
    private var iterator: AsyncStream<String>.Iterator
    private let continuation: AsyncStream<String>.Continuation
    private(set) var closed = false
    var sendError: Error?

    init() {
        var continuation: AsyncStream<String>.Continuation!
        let stream = AsyncStream<String> { continuation = $0 }
        self.continuation = continuation
        self.iterator = stream.makeAsyncIterator()
    }

    func push(_ text: String) {
        continuation.yield(text)
    }

    func dropConnection() {
        continuation.finish()
    }

    func send(text: String) async throws {
        if let sendError { throw sendError }
        lock.withLock { sent.append(text) }
    }

    func receiveText() async throws -> String {
        if let text = await iterator.next() {
            return text
        }
        throw WebSocketError.connectionClosed
    }

    func close() {
        closed = true
        continuation.finish()
    }

    var sentTexts: [String] {
        lock.withLock { sent }
    }
}

final class MockWebSocketConnectionFactory: WebSocketConnectionFactory, @unchecked Sendable {
    private let lock = NSLock()
    private var connections: [MockWebSocketConnection]
    private(set) var openedURLs: [URL] = []

    init(connections: [MockWebSocketConnection]) {
        self.connections = connections
    }

    func open(url: URL) -> WebSocketConnecting {
        lock.withLock {
            openedURLs.append(url)
            // Reuse the last scripted connection if the client reconnects
            // more times than the test scripted.
            return connections.count > 1 ? connections.removeFirst() : connections[0]
        }
    }
}

struct MockAccessTokenProvider: AccessTokenProviding {
    var token = "test-access-token"
    func currentAccessToken() async throws -> String { token }
}

/// TelemetryStreaming stub for SyncManager tests: records sends and lets
/// tests script connect/disconnect transitions.
final class MockTelemetryStream: TelemetryStreaming, @unchecked Sendable {
    private let lock = NSLock()
    private var received: [TelemetryEvent] = []
    private var connectionContinuations: [AsyncStream<StreamConnectionEvent>.Continuation] = []
    private var messageContinuations: [AsyncStream<WSServerMessage>.Continuation] = []
    var error: Error?

    func send(_ event: TelemetryEvent) async throws {
        if let error { throw error }
        lock.withLock { received.append(event) }
    }

    func connectionEvents() -> AsyncStream<StreamConnectionEvent> {
        AsyncStream { continuation in
            lock.withLock { connectionContinuations.append(continuation) }
        }
    }

    func serverMessages() -> AsyncStream<WSServerMessage> {
        AsyncStream { continuation in
            lock.withLock { messageContinuations.append(continuation) }
        }
    }

    func emitConnection(_ change: StreamConnectionEvent) {
        for continuation in lock.withLock({ connectionContinuations }) {
            continuation.yield(change)
        }
    }

    func emitServerMessage(_ message: WSServerMessage) {
        for continuation in lock.withLock({ messageContinuations }) {
            continuation.yield(message)
        }
    }

    var events: [TelemetryEvent] {
        lock.withLock { received }
    }
}

/// TelemetryUploading stub recording batch requests; event ids listed in
/// `rejectedIds` come back as permanently rejected.
final class MockTelemetryUploader: TelemetryUploading, @unchecked Sendable {
    private let lock = NSLock()
    private var recorded: [TelemetryBatchRequest] = []
    var error: Error?
    var rejectedIds: Set<UUID> = []

    func uploadTelemetryBatch(_ request: TelemetryBatchRequest) async throws -> BatchUploadResponse {
        if let error { throw error }
        lock.withLock { recorded.append(request) }
        let rejected = request.events.map(\.event).filter { rejectedIds.contains($0.eventId) }
        return BatchUploadResponse(
            accepted: true,
            batchId: request.batchId.uuidString,
            acceptedCount: request.events.count - rejected.count,
            rejectedCount: rejected.count,
            rejectedEvents: rejected.map {
                RejectedBatchEvent(eventId: $0.eventId.uuidString, reason: "validation_failed")
            }
        )
    }

    var requests: [TelemetryBatchRequest] {
        lock.withLock { recorded }
    }
}
