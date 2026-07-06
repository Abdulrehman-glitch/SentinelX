import SwiftUI

struct MainTabView: View {
    @EnvironmentObject private var container: AppContainer

    var body: some View {
        TabView {
            DeviceStatusView()
                .tabItem { Label("Status", systemImage: "gauge.with.dots.needle.50percent") }

            SettingsView()
                .tabItem { Label("Settings", systemImage: "gearshape") }
        }
    }
}

/// Placeholder until Phase 3 wires live collector cards in.
struct DeviceStatusView: View {
    var body: some View {
        NavigationStack {
            VStack(spacing: 12) {
                Image(systemName: "checkmark.shield")
                    .font(.system(size: 44))
                    .foregroundStyle(.green)
                Text("Connected")
                    .font(.title3.bold())
                Text("Telemetry collectors arrive in Phase 3.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            .navigationTitle("Device Status")
        }
    }
}
