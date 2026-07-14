import Foundation

/// Remote-controllable agent configuration (docs/spec/05 §26).
struct AgentConfig: Codable, Sendable, Equatable {
    let deviceId: String
    let configVersion: String
    let collectors: [String: CollectorConfig]
    let upload: UploadConfig

    enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
        case configVersion = "config_version"
        case collectors
        case upload
    }
}

struct CollectorConfig: Codable, Sendable, Equatable {
    let enabled: Bool
    let intervalSeconds: Int?
    let sampleHz: Int?
    let accuracy: String?

    enum CodingKeys: String, CodingKey {
        case enabled
        case intervalSeconds = "interval_seconds"
        case sampleHz = "sample_hz"
        case accuracy
    }

    init(enabled: Bool, intervalSeconds: Int? = nil, sampleHz: Int? = nil, accuracy: String? = nil) {
        self.enabled = enabled
        self.intervalSeconds = intervalSeconds
        self.sampleHz = sampleHz
        self.accuracy = accuracy
    }
}

struct UploadConfig: Codable, Sendable, Equatable {
    let websocketEnabled: Bool
    let restFallbackEnabled: Bool
    let batchSize: Int
    let flushIntervalSeconds: Int

    enum CodingKeys: String, CodingKey {
        case websocketEnabled = "websocket_enabled"
        case restFallbackEnabled = "rest_fallback_enabled"
        case batchSize = "batch_size"
        case flushIntervalSeconds = "flush_interval_seconds"
    }

    init(websocketEnabled: Bool, restFallbackEnabled: Bool, batchSize: Int, flushIntervalSeconds: Int) {
        self.websocketEnabled = websocketEnabled
        self.restFallbackEnabled = restFallbackEnabled
        self.batchSize = batchSize
        self.flushIntervalSeconds = flushIntervalSeconds
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        websocketEnabled = try container.decode(Bool.self, forKey: .websocketEnabled)
        // The contract's /config example omits this field — default to true.
        restFallbackEnabled = try container.decodeIfPresent(Bool.self, forKey: .restFallbackEnabled) ?? true
        batchSize = try container.decode(Int.self, forKey: .batchSize)
        flushIntervalSeconds = try container.decode(Int.self, forKey: .flushIntervalSeconds)
    }
}
