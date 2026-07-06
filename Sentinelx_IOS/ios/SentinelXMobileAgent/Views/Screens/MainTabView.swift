import SwiftUI

struct MainTabView: View {
    @EnvironmentObject private var container: AppContainer

    var body: some View {
        TabView {
            DeviceStatusView()
                .tabItem { Label("Status", systemImage: "gauge.with.dots.needle.50percent") }

            DebugStreamView(viewModel: container.makeTelemetryDebugViewModel())
                .tabItem { Label("Stream", systemImage: "dot.radiowaves.left.and.right") }

            SettingsView()
                .tabItem { Label("Settings", systemImage: "gearshape") }
        }
        .task {
            // Session is authenticated once this view exists: sync remote
            // config, then bring the pipeline and collectors up.
            await container.configurationService.refreshFromBackend()
            await container.startAgent()
        }
    }
}
