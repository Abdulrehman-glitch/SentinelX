import SwiftUI

/// Offline queue inspection (spec 06 Phase 5): live counts, oldest pending
/// age, last transport error, manual flush, and failed-event cleanup.
struct QueueSection: View {
    @StateObject private var viewModel: QueueViewModel
    @State private var confirmClear = false

    init(syncManager: SyncManager) {
        _viewModel = StateObject(wrappedValue: QueueViewModel(syncManager: syncManager))
    }

    var body: some View {
        Section {
            LabeledContent("Uplink", value: viewModel.streamConnected ? "Streaming" : "REST fallback")
                .task { await viewModel.poll() }
            LabeledContent("Pending", value: "\(viewModel.counts.pending)")
            LabeledContent("In flight", value: "\(viewModel.counts.inFlight)")
            LabeledContent("Failed", value: "\(viewModel.counts.failed)")
            if let oldest = viewModel.counts.oldestPendingAt {
                LabeledContent("Oldest pending") {
                    Text(oldest, style: .relative)
                }
            }
            if let lastError = viewModel.counts.lastError {
                LabeledContent("Last error") {
                    Text(lastError)
                        .font(.caption)
                        .lineLimit(3)
                        .foregroundStyle(.secondary)
                }
            }
            Button {
                Task { await viewModel.flushNow() }
            } label: {
                if viewModel.flushing {
                    ProgressView()
                } else {
                    Text("Flush Now")
                }
            }
            .disabled(viewModel.flushing)
            if viewModel.counts.failed > 0 {
                Button("Clear Failed", role: .destructive) {
                    confirmClear = true
                }
                .confirmationDialog(
                    "Delete \(viewModel.counts.failed) failed events?",
                    isPresented: $confirmClear,
                    titleVisibility: .visible
                ) {
                    Button("Delete", role: .destructive) {
                        Task { await viewModel.clearFailed() }
                    }
                }
            }
        } header: {
            Text("Offline Queue")
        } footer: {
            Text("Events persist here until the server acknowledges them. Failed events were rejected permanently or exhausted their retries.")
        }
    }
}
