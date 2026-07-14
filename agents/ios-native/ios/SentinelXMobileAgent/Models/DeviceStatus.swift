import Foundation

enum DeviceStatus: String, Codable, Sendable {
    case active
    case disabled
    case online
    case offline
    case pending
    case revoked
}
