import OSLog

/// Central OSLog handles. Never log tokens, device secrets, or precise
/// location payloads through these.
enum Log {
    private static let subsystem = Bundle.main.bundleIdentifier ?? "com.sentinelx.mobileagent"

    static let app = Logger(subsystem: subsystem, category: "app")
    static let auth = Logger(subsystem: subsystem, category: "auth")
    static let network = Logger(subsystem: subsystem, category: "network")
    static let telemetry = Logger(subsystem: subsystem, category: "telemetry")
    static let collectors = Logger(subsystem: subsystem, category: "collectors")
    static let persistence = Logger(subsystem: subsystem, category: "persistence")
}
