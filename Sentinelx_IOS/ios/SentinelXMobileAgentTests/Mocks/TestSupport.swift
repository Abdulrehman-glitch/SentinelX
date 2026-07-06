import Foundation
@testable import SentinelXMobileAgent

struct FixedDateProvider: DateProviding {
    let fixed: Date
    func now() -> Date { fixed }
}

struct FixedUUIDProvider: UUIDProviding {
    let fixed: UUID
    func uuid() -> UUID { fixed }
}

struct FixedDeviceInfoProvider: DeviceInfoProviding {
    func snapshot() -> DeviceInfoSnapshot {
        DeviceInfoSnapshot(
            deviceName: "Test iPhone",
            deviceModel: "iPhone15,2",
            systemName: "iOS",
            systemVersion: "17.5",
            localeIdentifier: "en_GB",
            timezoneIdentifier: "Europe/London",
            vendorIdentifier: "TEST-VENDOR-ID",
            screenWidth: 393,
            screenHeight: 852,
            screenScale: 3
        )
    }
}

/// Deterministic RNG (LCG) for jitter tests.
struct SeededRandomNumberGenerator: RandomNumberGenerator {
    private var state: UInt64

    init(seed: UInt64) {
        state = seed
    }

    mutating func next() -> UInt64 {
        state = state &* 6364136223846793005 &+ 1442695040888963407
        return state
    }
}

enum TestFixtures {
    static let baseURL = URL(string: "http://test.invalid/api/v1/mobile")!

    static func environment() -> AppEnvironment {
        AppEnvironment(
            apiBaseURL: baseURL,
            webSocketBaseURL: URL(string: "ws://test.invalid/api/v1/mobile/ws")!,
            agentVersion: "0.1.0-test",
            appBuild: "1",
            environmentName: "test"
        )
    }

    static let registrationResponseJSON = """
    {
      "device_id": "dev_TEST0001",
      "device_secret": "test-secret-value",
      "registered_at": "2026-07-06T12:00:00Z",
      "status": "active"
    }
    """

    static let tokenResponseJSON = """
    {
      "access_token": "test-access-token",
      "refresh_token": "test-refresh-token",
      "token_type": "bearer",
      "expires_in": 1800
    }
    """

    static let refreshedTokenResponseJSON = """
    {
      "access_token": "refreshed-access-token",
      "refresh_token": "refreshed-refresh-token",
      "token_type": "bearer",
      "expires_in": 1800
    }
    """

    static let profileJSON = """
    {
      "device_id": "dev_TEST0001",
      "platform": "ios",
      "device_name": "Test iPhone",
      "device_model": "iPhone15,2",
      "os_version": "iOS 17.5",
      "app_version": "0.1.0-test",
      "timezone": "Europe/London",
      "locale": "en_GB",
      "status": "active",
      "registered_at": "2026-07-06T12:00:00Z",
      "last_seen": "2026-07-06T12:05:00.123456+00:00"
    }
    """
}
