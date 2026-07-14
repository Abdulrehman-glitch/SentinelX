import Foundation

/// Runtime configuration for the agent. Defaults come from Info.plist
/// (populated by project.yml); the server URLs can be overridden at runtime
/// from the Settings screen so a physical device can point at a dev machine
/// on the local network without rebuilding.
struct AppEnvironment: Sendable {
    let apiBaseURL: URL
    let webSocketBaseURL: URL
    let agentVersion: String
    let appBuild: String
    let environmentName: String

    enum DefaultsKey {
        static let apiBaseURLOverride = "sentinelx.server.apiBaseURL"
        static let webSocketURLOverride = "sentinelx.server.webSocketURL"
        // Kill switch for consuming WS telemetry.ack (P5.3) — lets a device
        // build fall back to reconnect-requeue delivery without a rebuild.
        static let disableStreamAcks = "sentinelx.sync.disableStreamAcks"
    }

    static func load(
        bundle: Bundle = .main,
        defaults: UserDefaults = .standard
    ) -> AppEnvironment {
        let apiOverride = defaults.string(forKey: DefaultsKey.apiBaseURLOverride)
        let wsOverride = defaults.string(forKey: DefaultsKey.webSocketURLOverride)

        let apiDefault = bundle.object(forInfoDictionaryKey: "SentinelXDefaultAPIBaseURL") as? String
        let wsDefault = bundle.object(forInfoDictionaryKey: "SentinelXDefaultWebSocketURL") as? String

        // A malformed override falls back to the bundled default rather than
        // leaving the app unable to start.
        let apiBaseURL = Self.url(from: apiOverride)
            ?? Self.url(from: apiDefault)
            ?? URL(string: "http://127.0.0.1:8100/api/v1/mobile")!
        let webSocketBaseURL = Self.url(from: wsOverride)
            ?? Self.url(from: wsDefault)
            ?? URL(string: "ws://127.0.0.1:8100/api/v1/mobile/ws")!

        let version = bundle.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "0.0.0"
        let build = bundle.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "0"

        #if DEBUG
        let environmentName = "development"
        #else
        let environmentName = "production"
        #endif

        return AppEnvironment(
            apiBaseURL: apiBaseURL,
            webSocketBaseURL: webSocketBaseURL,
            agentVersion: version,
            appBuild: build,
            environmentName: environmentName
        )
    }

    private static func url(from string: String?) -> URL? {
        guard let string, !string.isEmpty, let url = URL(string: string), url.scheme != nil else {
            return nil
        }
        return url
    }
}
