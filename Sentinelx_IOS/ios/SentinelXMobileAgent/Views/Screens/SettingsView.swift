import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var container: AppContainer

    var body: some View {
        NavigationStack {
            SettingsContent(
                authService: container.authService,
                container: container,
                environment: container.environment
            )
            .navigationTitle("Settings")
        }
    }
}

private struct SettingsContent: View {
    @ObservedObject var authService: AuthService
    let container: AppContainer
    let environment: AppEnvironment

    // Runtime server overrides read by AppEnvironment.load() at next launch —
    // this is how a sideloaded phone build points at the dev laptop's LAN IP.
    @AppStorage(AppEnvironment.DefaultsKey.apiBaseURLOverride)
    private var apiURLOverride = ""
    @AppStorage(AppEnvironment.DefaultsKey.webSocketURLOverride)
    private var wsURLOverride = ""

    var body: some View {
        List {
            Section("Device") {
                LabeledContent("Device ID", value: deviceId)
                LabeledContent("Agent Version", value: environment.agentVersion)
                LabeledContent("Environment", value: environment.environmentName)
            }

            Section {
                LabeledContent("Active API") {
                    Text(environment.apiBaseURL.absoluteString)
                        .font(.caption)
                        .lineLimit(2)
                }
                TextField("API override (http://192.168.x.x:8100/api/v1/mobile)", text: $apiURLOverride)
                    .keyboardType(.URL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .font(.caption)
                TextField("WebSocket override (ws://192.168.x.x:8100/api/v1/mobile/ws)", text: $wsURLOverride)
                    .keyboardType(.URL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .font(.caption)
            } header: {
                Text("Server")
            } footer: {
                Text("Overrides apply after the app is relaunched. Leave empty to use the built-in defaults.")
            }

            Section {
                Button("Log Out", role: .destructive) {
                    Task {
                        // Spec §36: collectors stop before the session ends.
                        await container.stopAgent()
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
