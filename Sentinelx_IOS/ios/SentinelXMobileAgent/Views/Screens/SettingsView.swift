import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var container: AppContainer

    var body: some View {
        NavigationStack {
            SettingsContent(
                authService: container.authService,
                telemetryManager: container.telemetryManager,
                environment: container.environment
            )
            .navigationTitle("Settings")
        }
    }
}

private struct SettingsContent: View {
    @ObservedObject var authService: AuthService
    let telemetryManager: TelemetryManager
    let environment: AppEnvironment

    var body: some View {
        List {
            Section("Device") {
                LabeledContent("Device ID", value: deviceId)
                LabeledContent("Agent Version", value: environment.agentVersion)
                LabeledContent("Environment", value: environment.environmentName)
            }

            Section("Server") {
                LabeledContent("API") {
                    Text(environment.apiBaseURL.absoluteString)
                        .font(.caption)
                        .lineLimit(2)
                }
            }

            Section {
                Button("Log Out", role: .destructive) {
                    Task {
                        // Spec §36: collectors stop before the session ends.
                        await telemetryManager.stop()
                        await authService.logout()
                    }
                }
            } footer: {
                Text("Logging out clears session tokens but keeps this device registered.")
            }
        }
    }

    private var deviceId: String {
        if case .authenticated(let id) = authService.state { return id }
        return "—"
    }
}
