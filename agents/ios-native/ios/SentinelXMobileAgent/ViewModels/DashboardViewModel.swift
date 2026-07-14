import Foundation

@MainActor
final class DashboardViewModel: ObservableObject {
    @Published private(set) var latestByCategory: [TelemetryCategory: TelemetryEvent] = [:]
    @Published private(set) var healthReports: [CollectorHealth] = []

    private let telemetryManager: TelemetryManager
    private var streamTask: Task<Void, Never>?
    private var healthTask: Task<Void, Never>?

    init(telemetryManager: TelemetryManager) {
        self.telemetryManager = telemetryManager
    }

    func start() async {
        guard streamTask == nil else { return }

        for event in await telemetryManager.recentEvents() {
            latestByCategory[event.category] = event
        }
        healthReports = await telemetryManager.healthReports()

        streamTask = Task { [weak self, telemetryManager] in
            for await event in await telemetryManager.eventStream() {
                guard let self, !Task.isCancelled else { return }
                self.latestByCategory[event.category] = event
            }
        }

        // Health changes have no push channel yet; a light poll keeps the
        // chips honest without hammering the collectors.
        healthTask = Task { [weak self, telemetryManager] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(10))
                guard let self, !Task.isCancelled else { return }
                self.healthReports = await telemetryManager.healthReports()
            }
        }
    }

    func stop() {
        streamTask?.cancel()
        streamTask = nil
        healthTask?.cancel()
        healthTask = nil
    }

    func latest(_ category: TelemetryCategory) -> TelemetryEvent? {
        latestByCategory[category]
    }
}
