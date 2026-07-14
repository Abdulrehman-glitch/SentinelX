import Foundation

/// Request body for POST /batch (docs/spec/03 §14). Batch items must NOT
/// carry device_id — it comes from the envelope — so events are wrapped in
/// `BatchEventEnvelope`, which encodes everything except that field.
struct TelemetryBatchRequest: Encodable, Sendable {
    let deviceId: String
    let batchId: UUID
    let sentAt: Date
    let events: [BatchEventEnvelope]

    init(deviceId: String, batchId: UUID, sentAt: Date, events: [TelemetryEvent]) {
        self.deviceId = deviceId
        self.batchId = batchId
        self.sentAt = sentAt
        self.events = events.map(BatchEventEnvelope.init)
    }

    enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
        case batchId = "batch_id"
        case sentAt = "sent_at"
        case events
    }
}

struct BatchEventEnvelope: Encodable, Sendable {
    let event: TelemetryEvent

    enum CodingKeys: String, CodingKey {
        case eventId = "event_id"
        case timestamp, category, type, source, sequence, payload, metadata
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(event.eventId, forKey: .eventId)
        try container.encode(event.timestamp, forKey: .timestamp)
        try container.encode(event.category, forKey: .category)
        try container.encode(event.type, forKey: .type)
        try container.encode(event.source, forKey: .source)
        try container.encodeIfPresent(event.sequence, forKey: .sequence)
        try container.encode(event.payload, forKey: .payload)
        try container.encodeIfPresent(event.metadata, forKey: .metadata)
    }
}

/// Response to POST /batch.
struct BatchUploadResponse: Decodable, Sendable {
    let accepted: Bool
    let batchId: String
    let acceptedCount: Int
    let rejectedCount: Int
    let rejectedEvents: [RejectedBatchEvent]

    enum CodingKeys: String, CodingKey {
        case accepted
        case batchId = "batch_id"
        case acceptedCount = "accepted_count"
        case rejectedCount = "rejected_count"
        case rejectedEvents = "rejected_events"
    }
}

struct RejectedBatchEvent: Decodable, Sendable {
    let eventId: String
    let reason: String

    enum CodingKeys: String, CodingKey {
        case eventId = "event_id"
        case reason
    }
}
