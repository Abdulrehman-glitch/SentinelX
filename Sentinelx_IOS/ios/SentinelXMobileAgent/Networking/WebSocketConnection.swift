import Foundation

/// One live WebSocket. Abstracted so WebSocketClient tests run against a
/// scripted connection; each (re)connect opens a fresh instance.
protocol WebSocketConnecting: Sendable {
    func send(text: String) async throws
    func receiveText() async throws -> String
    func close()
}

protocol WebSocketConnectionFactory: Sendable {
    func open(url: URL) -> WebSocketConnecting
}

enum WebSocketError: Error, Equatable, Sendable {
    case notConnected
    case authRejected(reason: String)
    case connectionClosed
    case unexpectedMessage
}

/// URLSessionWebSocketTask-backed implementation.
final class URLSessionWebSocketConnection: WebSocketConnecting, @unchecked Sendable {
    private let task: URLSessionWebSocketTask

    init(url: URL, session: URLSession = .shared) {
        task = session.webSocketTask(with: url)
        task.resume()
    }

    func send(text: String) async throws {
        try await task.send(.string(text))
    }

    func receiveText() async throws -> String {
        switch try await task.receive() {
        case .string(let text):
            return text
        case .data(let data):
            guard let text = String(data: data, encoding: .utf8) else {
                throw WebSocketError.unexpectedMessage
            }
            return text
        @unknown default:
            throw WebSocketError.unexpectedMessage
        }
    }

    func close() {
        task.cancel(with: .normalClosure, reason: nil)
    }
}

struct URLSessionWebSocketConnectionFactory: WebSocketConnectionFactory {
    func open(url: URL) -> WebSocketConnecting {
        URLSessionWebSocketConnection(url: url)
    }
}
