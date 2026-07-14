import Foundation

/// Owns the set of collectors; TelemetryManager drives lifecycle through it.
actor CollectorRegistry {
    private var collectors: [any TelemetryCollector]

    /// Seeding at init is synchronous, so the registry is fully populated
    /// before TelemetryManager can possibly start.
    init(collectors: [any TelemetryCollector] = []) {
        self.collectors = collectors
    }

    func register(_ collector: any TelemetryCollector) {
        guard !collectors.contains(where: { $0.id == collector.id }) else {
            Log.collectors.warning("Duplicate collector registration ignored: \(collector.id, privacy: .public)")
            return
        }
        collectors.append(collector)
    }

    func allCollectors() -> [any TelemetryCollector] {
        collectors
    }

    func stopAll() async {
        for collector in collectors {
            await collector.stop()
        }
    }

    func healthReports() async -> [CollectorHealth] {
        var reports: [CollectorHealth] = []
        for collector in collectors {
            reports.append(await collector.healthStatus())
        }
        return reports
    }
}
