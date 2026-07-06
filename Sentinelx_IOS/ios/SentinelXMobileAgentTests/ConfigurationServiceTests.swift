import XCTest
@testable import SentinelXMobileAgent

final class ConfigurationServiceTests: XCTestCase {
    private let now = Date(timeIntervalSince1970: 1_800_000_000)

    private let remoteConfigJSON = """
    {
      "device_id": "dev_TEST0001",
      "config_version": "2.0",
      "collectors": {
        "battery": { "enabled": true, "interval_seconds": 15 },
        "motion": { "enabled": true, "sample_hz": 10 },
        "location": { "enabled": true, "interval_seconds": 5, "accuracy": "balanced" },
        "bluetooth": { "enabled": false }
      },
      "upload": {
        "websocket_enabled": true,
        "batch_size": 50,
        "flush_interval_seconds": 15
      }
    }
    """

    private func makeService(
        transport: MockHTTPTransport,
        defaults: UserDefaults
    ) async throws -> ConfigurationService {
        let keychain = InMemoryKeychain()
        let tokenStore = TokenStore(keychain: keychain, dateProvider: FixedDateProvider(fixed: now))
        try await tokenStore.save(
            TokenPair(accessToken: "a", refreshToken: "r", expiresAt: now.addingTimeInterval(1800))
        )
        let client = APIClient(
            environment: TestFixtures.environment(),
            transport: transport,
            tokenStore: tokenStore,
            deviceSecretStore: DeviceSecretStore(keychain: keychain),
            dateProvider: FixedDateProvider(fixed: now)
        )
        return ConfigurationService(apiClient: client, defaults: defaults)
    }

    private func freshDefaults() -> UserDefaults {
        UserDefaults(suiteName: "ConfigurationServiceTests-\(UUID().uuidString)")!
    }

    func testDefaultsArePrivacyFirst() async throws {
        let service = try await makeService(transport: MockHTTPTransport(), defaults: freshDefaults())
        let config = await service.currentConfig()

        XCTAssertEqual(config.configVersion, "local-default")
        XCTAssertEqual(config.collectors["battery"]?.enabled, true)
        XCTAssertEqual(config.collectors["location"]?.enabled, false)
        XCTAssertEqual(config.collectors["bluetooth"]?.enabled, false)
        XCTAssertEqual(config.collectors["motion"]?.enabled, false)
    }

    func testRefreshAppliesAndCachesRemoteConfig() async throws {
        let transport = MockHTTPTransport()
        transport.enqueue(.init(statusCode: 200, json: remoteConfigJSON))
        let defaults = freshDefaults()
        let service = try await makeService(transport: transport, defaults: defaults)

        let config = await service.refreshFromBackend()

        XCTAssertEqual(config.configVersion, "2.0")
        XCTAssertEqual(config.collectors["battery"]?.intervalSeconds, 15)
        // Omitted rest_fallback_enabled defaults to true.
        XCTAssertTrue(config.upload.restFallbackEnabled)

        // A fresh service over the same defaults must read the cache, not
        // the local default.
        let second = try await makeService(transport: MockHTTPTransport(), defaults: defaults)
        let cached = await second.currentConfig()
        XCTAssertEqual(cached.configVersion, "2.0")
    }

    func testRefreshFailureKeepsCurrentConfig() async throws {
        let transport = MockHTTPTransport()
        transport.enqueue(.init(statusCode: 500, json: #"{"error":{"code":"SERVER_ERROR","message":"boom"}}"#))
        let service = try await makeService(transport: transport, defaults: freshDefaults())

        let config = await service.refreshFromBackend()

        XCTAssertEqual(config.configVersion, "local-default")
    }

    func testTelemetryEventContractEncoding() throws {
        // Envelope snake_case check lives here alongside config coding tests.
        let event = TelemetryEvent(
            eventId: UUID(uuidString: "4F4F5F8D-8E9B-41C5-9A2A-7CC92B3A3C88")!,
            deviceId: "dev_TEST0001",
            timestamp: Date(timeIntervalSince1970: 1_800_000_000),
            category: .battery,
            type: "battery.snapshot",
            source: "ios.uidevice",
            sequence: 120,
            payload: .object(["level": .number(84), "charging": .bool(false)]),
            metadata: TelemetryMetadata(
                platform: .ios,
                agentVersion: "1.0.0",
                collectorVersion: "1.0.0",
                appBuild: "100",
                environment: "development"
            )
        )

        let data = try JSONCoding.encoder.encode(event)
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])

        XCTAssertEqual(object["event_id"] as? String, "4F4F5F8D-8E9B-41C5-9A2A-7CC92B3A3C88")
        XCTAssertEqual(object["device_id"] as? String, "dev_TEST0001")
        XCTAssertEqual(object["category"] as? String, "battery")
        XCTAssertEqual(object["type"] as? String, "battery.snapshot")
        XCTAssertEqual(object["source"] as? String, "ios.uidevice")
        XCTAssertEqual(object["sequence"] as? Int, 120)
        let payload = try XCTUnwrap(object["payload"] as? [String: Any])
        XCTAssertEqual(payload["level"] as? Double, 84)
        let metadata = try XCTUnwrap(object["metadata"] as? [String: Any])
        XCTAssertEqual(metadata["agent_version"] as? String, "1.0.0")
        XCTAssertEqual(metadata["platform"] as? String, "ios")

        let decoded = try JSONCoding.decoder.decode(TelemetryEvent.self, from: data)
        XCTAssertEqual(decoded, event)
    }
}
