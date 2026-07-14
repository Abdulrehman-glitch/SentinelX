import Foundation

/// Envelope validation applied before an event is accepted into the
/// pipeline (docs/spec/05 §34 client-side subset).
enum TelemetryEventValidator {
    enum ValidationError: Error, Equatable {
        case deviceIdMismatch
        case payloadNotObject
        case emptyType
        case emptySource
        case timestampTooFarInFuture
    }

    /// Events must not claim to come from the future (small clock drift is
    /// tolerated); staleness limits are enforced server-side.
    static let allowedFutureDrift: TimeInterval = 300

    static func validate(
        _ event: TelemetryEvent,
        expectedDeviceId: String,
        now: Date
    ) -> ValidationError? {
        guard event.deviceId == expectedDeviceId else { return .deviceIdMismatch }
        guard case .object = event.payload else { return .payloadNotObject }
        guard !event.type.isEmpty else { return .emptyType }
        guard !event.source.isEmpty else { return .emptySource }
        guard event.timestamp.timeIntervalSince(now) <= allowedFutureDrift else {
            return .timestampTooFarInFuture
        }
        return nil
    }
}
