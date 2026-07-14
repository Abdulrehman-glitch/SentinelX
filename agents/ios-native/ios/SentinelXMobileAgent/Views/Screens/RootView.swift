import SwiftUI

struct RootView: View {
    @EnvironmentObject private var container: AppContainer

    var body: some View {
        SessionSwitchView(authService: container.authService)
    }
}

/// Routes on the published session state; separated so @ObservedObject can
/// bind to the concrete AuthService owned by the container.
private struct SessionSwitchView: View {
    @ObservedObject var authService: AuthService
    @EnvironmentObject private var container: AppContainer

    var body: some View {
        Group {
            switch authService.state {
            case .unknown:
                ProgressView("Starting…")
            case .authenticated:
                MainTabView()
            case .needsRegistration, .registered, .authenticating:
                LoginView(viewModel: container.makeAuthViewModel())
            }
        }
        .task { await authService.bootstrapIfNeeded() }
    }
}
