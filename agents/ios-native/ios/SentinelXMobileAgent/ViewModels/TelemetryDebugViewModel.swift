import Foundation

@MainActor
final class TelemetryDebugViewModel: ObservableObject {
    @Published private(set) var events: [TelemetryEvent] = []
    @Published private(set) var acceptedCount = 0
    @Published private(set) var rejectedCount = 0

    private let telemetryManager: TelemetryManager
    private var streamTask: Task<Void, Never>?
    private let displayLimit = 200

    init(telemetryManager: TelemetryManager) {
        self.telemetryManager = telemetryManager
    }

    func startObserving() async {
        guard streamTask == nil else { return }

        let recent = await telemetryManager.recentEvents()
        events = recent.reversed()
        acceptedCount = await telemetryManager.acceptedCount
        rejectedCount = await telemetryManager.rejectedCount

        streamTask = Task { [weak self, telemetryManager] in
            for await event in await telemetryManager.eventStream() {
                guard let self, !Task.isCancelled else { return }
                self.prepend(event)
            }
        }
    }

    func stopObserving() {
        streamTask?.cancel()
        streamTask = nil
    }

    private func prepend(_ event: TelemetryEvent) {
        events.insert(event, at: 0)
        if events.count > displayLimit {
            events.removeLast(events.count - displayLimit)
        }
        acceptedCount += 1
    }
}
