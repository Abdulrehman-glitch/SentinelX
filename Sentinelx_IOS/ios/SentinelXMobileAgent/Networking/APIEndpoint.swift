import Foundation

/// Describes one REST endpoint relative to the mobile API base URL.
struct APIEndpoint: Sendable {
    enum Method: String, Sendable {
        case get = "GET"
        case post = "POST"
    }

    let method: Method
    let path: String
    let requiresAuth: Bool

    // Contract endpoints (docs/spec/03_Backend_API.md)
    static let register = APIEndpoint(method: .post, path: "register", requiresAuth: false)
    static let login = APIEndpoint(method: .post, path: "login", requiresAuth: false)
    static let refreshToken = APIEndpoint(method: .post, path: "token/refresh", requiresAuth: false)
    static let profile = APIEndpoint(method: .get, path: "profile", requiresAuth: true)
    static let telemetryBatch = APIEndpoint(method: .post, path: "batch", requiresAuth: true)
    static let config = APIEndpoint(method: .get, path: "config", requiresAuth: true)
}
