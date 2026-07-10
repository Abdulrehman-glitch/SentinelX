import Foundation

// Request/response DTOs for the /api/v1/mobile contract (docs/spec/03, 05).
// JSON is snake_case, Swift is camelCase — mapped with explicit CodingKeys.

struct DeviceRegistrationRequest: Codable, Sendable, Equatable {
    let platform: Platform
    let deviceName: String
    let deviceModel: String
    let osVersion: String
    let appVersion: String
    let vendorIdentifier: String
    let timezone: String
    let locale: String

    enum CodingKeys: String, CodingKey {
        case platform
        case deviceName = "device_name"
        case deviceModel = "device_model"
        case osVersion = "os_version"
        case appVersion = "app_version"
        case vendorIdentifier = "vendor_identifier"
        case timezone
        case locale
    }
}

struct DeviceRegistrationResponse: Codable, Sendable {
    let deviceId: String
    /// Returned exactly once at registration; goes straight to the Keychain.
    let deviceSecret: String
    let registeredAt: Date
    let status: DeviceStatus

    enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
        case deviceSecret = "device_secret"
        case registeredAt = "registered_at"
        case status
    }
}

struct LoginRequest: Codable, Sendable {
    let deviceId: String
    let deviceSecret: String

    enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
        case deviceSecret = "device_secret"
    }
}

struct TokenRefreshRequest: Codable, Sendable {
    let refreshToken: String

    enum CodingKeys: String, CodingKey {
        case refreshToken = "refresh_token"
    }
}

struct TokenResponse: Codable, Sendable {
    let accessToken: String
    let refreshToken: String
    let tokenType: String
    let expiresIn: Int

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case tokenType = "token_type"
        case expiresIn = "expires_in"
    }
}

struct APIErrorResponse: Codable, Sendable {
    let error: APIErrorDetail
}

struct APIErrorDetail: Codable, Sendable {
    let code: String
    let message: String
    let details: JSONValue?
    let requestId: String?

    enum CodingKeys: String, CodingKey {
        case code
        case message
        case details
        case requestId = "request_id"
    }
}
