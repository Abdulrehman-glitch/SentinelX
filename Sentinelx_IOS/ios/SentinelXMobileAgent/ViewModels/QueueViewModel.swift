import Foundation

/// Snapshot view of the offline queue for the Settings inspection section.
/// `poll()` is designed to live in a SwiftUI `.task` — it refreshes until
/// the hosting row disappears and resumes when it comes back.
@MainActor
final class QueueViewModel: ObservableObject {
    @Published private(set) var counts = QueueCounts()
    @Published private(set) var stats = SyncStats()
    @Published private(set) var streamConnected = false
    @Published private(set) var flushing = false

    private let syncManager: SyncManager
    private let pollInterval: TimeInterval

    init(syncManager: SyncManager, pollInterval: TimeInterval = 2) {
        self.syncManager = syncManager
        self.pollInterval = pollInterval
    }

    func poll() async {
        await refresh()
        while !Task.isCancelled {
            try? await Task.sleep(for: .seconds(pollInterval))
            guard !Task.isCancelled else { return }
            await refresh()
        }
    }

    func flushNow() async {
        flushing = true
        await syncManager.flushNow()
        await refresh()
        flushing = false
    }

    func clearFailed() async {
        await syncManager.clearFailed()
        await refresh()
    }

    func refresh() async {
        counts = await syncManager.queueCounts()
        stats = await syncManager.stats
        streamConnected = await syncManager.streamConnected
    }
}
