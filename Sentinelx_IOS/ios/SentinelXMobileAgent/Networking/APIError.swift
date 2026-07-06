import Foundation

enum APIError: Error, Equatable, Sendable {
    case unauthorized
    case forbidden
    case notFound
    case validation(String)
    case rateLimited(retryAfterSeconds: Int?)
    case server(String)
    case backend(code: String, message: String)
    case decodingFailed
    case networkUnavailable
    case invalidResponse

    /// Safe to retry automatically; auth and validation failures are not.
    var isRetryable: Bool {
        switch self {
        case .rateLimited, .server, .networkUnavailable:
            return true
        case .unauthorized, .forbidden, .notFound, .validation,
             .backend, .decodingFailed, .invalidResponse:
            return false
        }
    }

    /// Non-technical message for the UI. Technical detail stays in logs.
    var userMessage: String {
        switch self {
        case .unauthorized:
            return "This device needs to sign in again."
        case .forbidden:
            return "This device is not allowed to do that."
        case .notFound:
            return "The server could not find this device."
        case .validation(let message):
            return message
        case .rateLimited:
            return "Sending too fast — please wait a moment."
        case .server:
            return "The server had a problem. Try again shortly."
        case .backend(_, let message):
            return message
        case .decodingFailed, .invalidResponse:
            return "Received an unexpected response from the server."
        case .networkUnavailable:
            return "No network connection."
        }
    }
}
