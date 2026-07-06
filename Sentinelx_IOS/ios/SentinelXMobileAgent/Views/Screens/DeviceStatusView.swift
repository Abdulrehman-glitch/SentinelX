import SwiftUI

/// Live device dashboard: latest reading per collector plus health chips.
struct DeviceStatusView: View {
    @EnvironmentObject private var container: AppContainer

    var body: some View {
        NavigationStack {
            DeviceStatusContent(viewModel: DashboardViewModel(telemetryManager: containerManager))
                .navigationTitle("Device Status")
        }
    }

    private var containerManager: TelemetryManager {
        container.telemetryManager
    }
}

private struct DeviceStatusContent: View {
    @StateObject private var viewModel: DashboardViewModel

    init(viewModel: @autoclosure @escaping () -> DashboardViewModel) {
        _viewModel = StateObject(wrappedValue: viewModel())
    }

    private let columns = [GridItem(.flexible()), GridItem(.flexible())]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                LazyVGrid(columns: columns, spacing: 12) {
                    batteryCard
                    thermalCard
                    storageCard
                    networkCard
                }

                if let device = viewModel.latest(.device)?.payload {
                    deviceSection(device)
                }

                if !viewModel.healthReports.isEmpty {
                    healthSection
                }
            }
            .padding()
        }
        .task { await viewModel.start() }
        .onDisappear { viewModel.stop() }
    }

    // MARK: - Cards

    private var batteryCard: some View {
        let payload = viewModel.latest(.battery)?.payload
        let level = payload?["level"]?.intValue
        let charging = payload?["charging"]?.boolValue ?? false
        let lowPower = payload?["low_power_mode"]?.boolValue ?? false

        return StatusCard(
            title: "Battery",
            systemImage: charging ? "battery.100.bolt" : "battery.75",
            value: level.map { "\($0)%" } ?? "—",
            caption: lowPower ? "Low Power Mode" : (charging ? "Charging" : "On battery"),
            tint: (level ?? 100) <= 20 ? .red : .green
        )
    }

    private var thermalCard: some View {
        let state = viewModel.latest(.thermal)?.payload["state"]?.stringValue

        let tint: Color = switch state {
        case "serious": .orange
        case "critical": .red
        default: .blue
        }
        return StatusCard(
            title: "Thermal",
            systemImage: "thermometer.medium",
            value: state?.capitalized ?? "—",
            caption: nil,
            tint: tint
        )
    }

    private var storageCard: some View {
        let payload = viewModel.latest(.storage)?.payload
        let freeBytes = payload?["free_bytes"]?.numberValue
        let freePercent = payload?["free_percent"]?.numberValue

        return StatusCard(
            title: "Storage",
            systemImage: "internaldrive",
            value: freeBytes.map { Self.gigabytes($0) + " free" } ?? "—",
            caption: freePercent.map { String(format: "%.1f%% available", $0) },
            tint: (freePercent ?? 100) < 10 ? .red : .indigo
        )
    }

    private var networkCard: some View {
        let payload = viewModel.latest(.network)?.payload
        let reachable = payload?["reachable"]?.boolValue
        let interface = payload?["interface"]?.stringValue

        return StatusCard(
            title: "Network",
            systemImage: interface == "cellular" ? "antenna.radiowaves.left.and.right" : "wifi",
            value: interface?.replacingOccurrences(of: "_", with: " ").capitalized ?? "—",
            caption: reachable == false ? "Offline" : "Reachable",
            tint: reachable == false ? .red : .teal
        )
    }

    private func deviceSection(_ payload: JSONValue) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Device")
                .font(.headline)
            Grid(alignment: .leading, horizontalSpacing: 16, verticalSpacing: 4) {
                infoRow("Model", payload["device_model"]?.stringValue)
                infoRow("System", systemDescription(payload))
                infoRow("Locale", payload["locale"]?.stringValue)
                infoRow("Timezone", payload["timezone"]?.stringValue)
            }
            .font(.subheadline)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 14))
    }

    private func systemDescription(_ payload: JSONValue) -> String? {
        guard let name = payload["system_name"]?.stringValue else { return nil }
        let version = payload["system_version"]?.stringValue ?? ""
        return "\(name) \(version)"
    }

    private func infoRow(_ label: String, _ value: String?) -> some View {
        GridRow {
            Text(label).foregroundStyle(.secondary)
            Text(value ?? "—")
        }
    }

    // MARK: - Health

    private var healthSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Collectors")
                .font(.headline)
            ForEach(viewModel.healthReports) { report in
                HStack {
                    Circle()
                        .fill(color(for: report.health))
                        .frame(width: 8, height: 8)
                    Text(report.collectorId.capitalized)
                        .font(.subheadline)
                    Spacer()
                    Text(label(for: report.health))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 14))
    }

    private func color(for state: CollectorHealthState) -> Color {
        switch state {
        case .healthy: .green
        case .degraded: .orange
        case .disabled: .gray
        case .permissionDenied: .yellow
        case .unsupported: .gray
        case .failed: .red
        }
    }

    private func label(for state: CollectorHealthState) -> String {
        switch state {
        case .permissionDenied: "Permission needed"
        default: state.rawValue.capitalized
        }
    }

    private static func gigabytes(_ bytes: Double) -> String {
        String(format: "%.1f GB", bytes / 1_000_000_000)
    }
}
