import Foundation

/// Composition root. Builds every service once at launch and hands them to
/// ViewModels through factory methods, so nothing reaches for globals.
@MainActor
final class AppContainer: ObservableObject {
    let environment: AppEnvironment

    init(environment: AppEnvironment = .load()) {
        self.environment = environment
    }
}
