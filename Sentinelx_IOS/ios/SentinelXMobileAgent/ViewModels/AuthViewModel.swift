import Combine
import Foundation

@MainActor
final class AuthViewModel: ObservableObject {
    @Published var serverAddress: String
    @Published private(set) var serverAddressSaved = false

    private let authService: AuthService
    private let environment: AppEnvironment
    private let defaults: UserDefaults
    private var cancellables: Set<AnyCancellable> = []

    var state: AuthService.SessionState { authService.state }
    var errorMessage: String? { authService.lastErrorMessage }

    init(authService: AuthService, environment: AppEnvironment, defaults: UserDefaults = .standard) {
        self.authService = authService
        self.environment = environment
        self.defaults = defaults
        self.serverAddress = defaults.string(forKey: AppEnvironment.DefaultsKey.apiBaseURLOverride)
            ?? environment.apiBaseURL.absoluteString

        // Re-publish service changes so the view re-renders on state moves.
        authService.objectWillChange
            .sink { [weak self] _ in self?.objectWillChange.send() }
            .store(in: &cancellables)
    }

    func register() async {
        await authService.registerAndLogin()
    }

    func connect() async {
        await authService.login()
    }

    func resetDeviceIdentity() async {
        await authService.resetDeviceIdentity()
    }

    /// Persists the server override; picked up on next launch when
    /// AppEnvironment is loaded (the service graph binds URLs at startup).
    func saveServerAddress() {
        let trimmed = serverAddress.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: trimmed), url.scheme != nil else { return }
        defaults.set(trimmed, forKey: AppEnvironment.DefaultsKey.apiBaseURLOverride)

        // Derive the matching WebSocket URL so the two never drift apart.
        var wsAddress = trimmed
        if wsAddress.hasPrefix("https://") {
            wsAddress = "wss://" + wsAddress.dropFirst("https://".count)
        } else if wsAddress.hasPrefix("http://") {
            wsAddress = "ws://" + wsAddress.dropFirst("http://".count)
        }
        defaults.set(wsAddress + "/ws", forKey: AppEnvironment.DefaultsKey.webSocketURLOverride)
        serverAddressSaved = true
    }
}
