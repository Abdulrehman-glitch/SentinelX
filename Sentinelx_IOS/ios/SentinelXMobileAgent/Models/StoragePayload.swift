import Foundation

/// Payload for `storage.snapshot` events.
struct StoragePayload: Codable, Sendable, Equatable {
    let totalBytes: Int64
    let freeBytes: Int64
    let usedBytes: Int64
    let freePercent: Double

    enum CodingKeys: String, CodingKey {
        case totalBytes = "total_bytes"
        case freeBytes = "free_bytes"
        case usedBytes = "used_bytes"
        case freePercent = "free_percent"
    }
}
