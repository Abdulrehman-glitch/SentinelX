import Foundation

enum AppConstants {
    static let keychainService = "com.sentinelx.mobileagent"

    static let heartbeatIntervalSeconds: TimeInterval = 30
    static let defaultBatchSize = 100
    static let defaultFlushIntervalSeconds = 30

    /// Refresh the access token this many seconds before it actually expires
    /// so an in-flight request never races the expiry.
    static let tokenExpiryLeewaySeconds: TimeInterval = 60
}
