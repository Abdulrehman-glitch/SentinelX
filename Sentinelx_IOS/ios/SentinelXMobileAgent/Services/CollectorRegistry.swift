import Foundation

/// Owns the set of collectors; TelemetryManager drives lifecycle through it.
actor CollectorRegistry {
    private var collectors: [any TelemetryCollector] = []

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

    func collector(withId id: String) -> (any TelemetryCollector)? {
        collectors.first { $0.id == id }
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
