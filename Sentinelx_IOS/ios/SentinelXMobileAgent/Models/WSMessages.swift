import Foundation

/// Client → server WebSocket messages (docs/spec/03 §16–19).
enum WSClientMessage {
    struct Auth: Encodable {
        let type = "auth"
        let accessToken: String
        let deviceId: String

        enum CodingKeys: String, CodingKey {
            case type
            case accessToken = "access_token"
            case deviceId = "device_id"
        }
    }

    struct Heartbeat: Encodable {
        let type = "heartbeat"
        let deviceId: String
        let timestamp: Date

        enum CodingKeys: String, CodingKey {
            case type
            case deviceId = "device_id"
            case timestamp
        }
    }

    struct TelemetryEventMessage: Encodable {
        let type = "telemetry.event"
        let event: TelemetryEvent
    }
}

/// Server → client messages, decoded by their `type` discriminator. Types
/// the app doesn't consume yet (config.update, commands) surface as
/// `.unhandled` so later phases can adopt them without protocol changes.
enum WSServerMessage: Equatable, Sendable {
    case authAccepted(deviceId: String, serverTime: String)
    case authRejected(reason: String)
    case heartbeatAck(serverTime: String)
    case telemetryAck(eventIds: [UUID], serverTime: String)
    case serverError(code: String, message: String)
    case alertCreated(JSONValue)
    case unhandled(type: String)

    private enum CodingKeys: String, CodingKey {
        case type, reason, code, message, alert
        case deviceId = "device_id"
        case serverTime = "server_time"
        case eventIds = "event_ids"
    }
}

extension WSServerMessage: Decodable {
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let type = try container.decode(String.self, forKey: .type)
        switch type {
        case "auth.accepted":
            self = .authAccepted(
                deviceId: try container.decode(String.self, forKey: .deviceId),
                serverTime: try container.decodeIfPresent(String.self, forKey: .serverTime) ?? ""
            )
        case "auth.rejected":
            self = .authRejected(
                reason: try container.decodeIfPresent(String.self, forKey: .reason) ?? "UNKNOWN"
            )
        case "heartbeat.ack":
            self = .heartbeatAck(
                serverTime: try container.decodeIfPresent(String.self, forKey: .serverTime) ?? ""
            )
        case "telemetry.ack":
            // Non-UUID ids are dropped rather than failing the frame.
            let raw = try container.decodeIfPresent([String].self, forKey: .eventIds) ?? []
            self = .telemetryAck(
                eventIds: raw.compactMap(UUID.init(uuidString:)),
                serverTime: try container.decodeIfPresent(String.self, forKey: .serverTime) ?? ""
            )
        case "error":
            self = .serverError(
                code: try container.decodeIfPresent(String.self, forKey: .code) ?? "SERVER_ERROR",
                message: try container.decodeIfPresent(String.self, forKey: .message) ?? ""
            )
        case "alert.created":
            self = .alertCreated(try container.decodeIfPresent(JSONValue.self, forKey: .alert) ?? .null)
        default:
            self = .unhandled(type: type)
        }
    }
}
