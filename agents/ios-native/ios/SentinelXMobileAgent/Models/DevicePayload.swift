import Foundation

/// Payload for `device.snapshot` events.
struct DevicePayload: Codable, Sendable, Equatable {
    let deviceName: String
    let deviceModel: String
    let systemName: String
    let systemVersion: String
    let locale: String
    let timezone: String
    let screenWidth: Double
    let screenHeight: Double
    let screenScale: Double

    enum CodingKeys: String, CodingKey {
        case deviceName = "device_name"
        case deviceModel = "device_model"
        case systemName = "system_name"
        case systemVersion = "system_version"
        case locale
        case timezone
        case screenWidth = "screen_width"
        case screenHeight = "screen_height"
        case screenScale = "screen_scale"
    }
}
