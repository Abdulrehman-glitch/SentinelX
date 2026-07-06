import Foundation

/// Everything a collector needs to build a complete, correctly-stamped
/// telemetry event. Handed over by TelemetryManager at start.
struct TelemetryContext: Sendable {
    let deviceId: String
    let metadata: TelemetryMetadata
    let uuidProvider: UUIDProviding
    let dateProvider: DateProviding

    func makeEvent(
        category: TelemetryCategory,
        type: String,
        source: String,
        payload: JSONValue
    ) -> TelemetryEvent {
        TelemetryEvent(
            eventId: uuidProvider.uuid(),
            deviceId: deviceId,
            timestamp: dateProvider.now(),
            category: category,
            type: type,
            source: source,
            sequence: nil,
            payload: payload,
            metadata: metadata
        )
    }
}

/// Sink collectors emit into. TelemetryManager conforms; collectors never
/// talk to the network or the queue directly.
protocol TelemetryEmitting: Sendable {
    func emit(_ event: TelemetryEvent) async
}

/// Contract for every telemetry collector (docs/spec/04 §7, adapted to
/// actor isolation: state accessors are async, identity is nonisolated).
protocol TelemetryCollector: Sendable {
    nonisolated var id: String { get }
    nonisolated var category: TelemetryCategory { get }

    /// Called once before start; collectors keep the context and emitter.
    func prepare(context: TelemetryContext, emitter: any TelemetryEmitting) async
    /// Remote/local configuration; may arrive before or while running.
    func apply(_ config: CollectorConfig) async

    func isEnabled() async -> Bool
    func start() async
    func stop() async
    func latestValue() async -> TelemetryEvent?
    func healthStatus() async -> CollectorHealth
}
