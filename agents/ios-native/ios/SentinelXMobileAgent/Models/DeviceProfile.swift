import Foundation

struct DeviceProfile: Codable, Identifiable, Sendable, Equatable {
    var id: String { deviceId }

    let deviceId: String
    let platform: Platform
    let deviceName: String
    let deviceModel: String
    let osVersion: String
    let appVersion: String
    let timezone: String?
    let locale: String?
    let status: DeviceStatus
    let registeredAt: Date?
    let lastSeen: Date?

    enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
        case platform
        case deviceName = "device_name"
        case deviceModel = "device_model"
        case osVersion = "os_version"
        case appVersion = "app_version"
        case timezone
        case locale
        case status
        case registeredAt = "registered_at"
        case lastSeen = "last_seen"
    }
}
