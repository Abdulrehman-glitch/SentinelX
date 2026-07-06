import Foundation
@testable import SentinelXMobileAgent

/// Scriptable collector for TelemetryManager tests.
actor MockCollector: TelemetryCollector {
    nonisolated let id: String
    nonisolated let category: TelemetryCategory

    private(set) var context: TelemetryContext?
    private(set) var emitter: (any TelemetryEmitting)?
    private(set) var appliedConfig: CollectorConfig?
    private(set) var startCount = 0
    private(set) var stopCount = 0
    private var enabled: Bool
    private var lastEvent: TelemetryEvent?

    init(id: String, category: TelemetryCategory, enabled: Bool = true) {
        self.id = id
        self.category = category
        self.enabled = enabled
    }

    func prepare(context: TelemetryContext, emitter: any TelemetryEmitting) async {
        self.context = context
        self.emitter = emitter
    }

    func apply(_ config: CollectorConfig) async {
        appliedConfig = config
        enabled = config.enabled
    }

    func isEnabled() async -> Bool { enabled }

    func start() async { startCount += 1 }

    func stop() async { stopCount += 1 }

    func latestValue() async -> TelemetryEvent? { lastEvent }

    func healthStatus() async -> CollectorHealth {
        CollectorHealth(
            collectorId: id,
            category: category,
            enabled: enabled,
            health: enabled ? .healthy : .disabled,
            lastEventAt: lastEvent?.timestamp,
            errorMessage: nil
        )
    }

    /// Test hook: emit a payload through the prepared context/emitter the
    /// way a real collector would.
    func emitSample(payload: JSONValue = .object(["value": .number(1)])) async {
        guard let context, let emitter else { return }
        let event = context.makeEvent(
            category: category,
            type: "\(category.rawValue).snapshot",
            source: "test.\(id)",
            payload: payload
        )
        lastEvent = event
        await emitter.emit(event)
    }

    /// Test hook: emit a pre-built (possibly invalid) event unchanged.
    func emitRaw(_ event: TelemetryEvent) async {
        await emitter?.emit(event)
    }
}
