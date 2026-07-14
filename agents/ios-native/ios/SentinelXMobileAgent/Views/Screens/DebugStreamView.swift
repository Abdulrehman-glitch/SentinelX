import SwiftUI

/// Live feed of accepted telemetry events — the Phase 2 acceptance surface
/// and a permanent diagnostics tool.
struct DebugStreamView: View {
    @StateObject private var viewModel: TelemetryDebugViewModel

    init(viewModel: @autoclosure @escaping () -> TelemetryDebugViewModel) {
        _viewModel = StateObject(wrappedValue: viewModel())
    }

    var body: some View {
        NavigationStack {
            Group {
                if viewModel.events.isEmpty {
                    ContentUnavailableView(
                        "No telemetry yet",
                        systemImage: "dot.radiowaves.left.and.right",
                        description: Text("Events appear here as collectors emit them.")
                    )
                } else {
                    List(viewModel.events) { event in
                        TelemetryEventRow(event: event)
                    }
                    .listStyle(.plain)
                }
            }
            .navigationTitle("Event Stream")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Text("\(viewModel.acceptedCount)")
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                }
            }
        }
        .task { await viewModel.startObserving() }
        .onDisappear { viewModel.stopObserving() }
    }
}

private struct TelemetryEventRow: View {
    let event: TelemetryEvent

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(event.type)
                    .font(.subheadline.weight(.semibold))
                Spacer()
                Text(event.timestamp, format: .dateTime.hour().minute().second())
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
            }
            Text(payloadSummary)
                .font(.caption.monospaced())
                .foregroundStyle(.secondary)
                .lineLimit(2)
        }
        .padding(.vertical, 2)
    }

    private var payloadSummary: String {
        guard let object = event.payload.objectValue else { return "—" }
        return object
            .sorted { $0.key < $1.key }
            .map { key, value in "\(key)=\(shortDescription(of: value))" }
            .joined(separator: "  ")
    }

    private func shortDescription(of value: JSONValue) -> String {
        switch value {
        case .string(let string): return string
        case .number(let number):
            return number.truncatingRemainder(dividingBy: 1) == 0
                ? String(Int(number))
                : String(format: "%.2f", number)
        case .bool(let bool): return bool ? "true" : "false"
        case .object: return "{…}"
        case .array(let items): return "[\(items.count)]"
        case .null: return "null"
        }
    }
}
