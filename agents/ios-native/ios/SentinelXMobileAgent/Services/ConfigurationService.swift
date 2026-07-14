import Foundation

/// Layered agent configuration: privacy-first local defaults, overridden by
/// the backend's /config response, cached (non-sensitive) in UserDefaults so
/// the last known config survives offline launches.
actor ConfigurationService {
    private enum CacheKey {
        static let config = "sentinelx.config.cache"
    }

    private let apiClient: APIClient
    private let defaults: UserDefaults
    private var cached: AgentConfig?

    init(apiClient: APIClient, defaults: UserDefaults = .standard) {
        self.apiClient = apiClient
        self.defaults = defaults
    }

    func currentConfig() -> AgentConfig {
        if let cached {
            return cached
        }
        if let data = defaults.data(forKey: CacheKey.config),
           let stored = try? JSONCoding.decoder.decode(AgentConfig.self, from: data) {
            cached = stored
            return stored
        }
        return Self.defaultConfig
    }

    /// Pulls remote config; on any failure the current (cached or default)
    /// config stays in effect — config sync must never take collectors down.
    @discardableResult
    func refreshFromBackend() async -> AgentConfig {
        do {
            let config = try await apiClient.fetchConfig()
            cached = config
            if let data = try? JSONCoding.encoder.encode(config) {
                defaults.set(data, forKey: CacheKey.config)
            }
            Log.telemetry.info("Remote config applied, version \(config.configVersion, privacy: .public)")
            return config
        } catch {
            Log.telemetry.warning("Config refresh failed, keeping current: \(String(describing: error), privacy: .public)")
            return currentConfig()
        }
    }

    /// Privacy-first defaults: sensors that need a permission prompt
    /// (motion, location) or are intrusive (bluetooth) stay off until the
    /// user or backend enables them.
    static let defaultConfig = AgentConfig(
        deviceId: "",
        configVersion: "local-default",
        collectors: [
            "device": CollectorConfig(enabled: true),
            "battery": CollectorConfig(enabled: true, intervalSeconds: 30),
            "thermal": CollectorConfig(enabled: true),
            "storage": CollectorConfig(enabled: true, intervalSeconds: 60),
            "network": CollectorConfig(enabled: true),
            "motion": CollectorConfig(enabled: false, sampleHz: 20),
            "activity": CollectorConfig(enabled: false),
            "location": CollectorConfig(enabled: false, intervalSeconds: 5, accuracy: "balanced"),
            "bluetooth": CollectorConfig(enabled: false),
            "metrickit": CollectorConfig(enabled: true),
        ],
        upload: UploadConfig(
            websocketEnabled: true,
            restFallbackEnabled: true,
            batchSize: AppConstants.defaultBatchSize,
            flushIntervalSeconds: AppConstants.defaultFlushIntervalSeconds
        )
    )
}
