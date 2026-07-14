import XCTest
@testable import SentinelXMobileAgent

/// Payloads must serialise exactly to the snake_case shapes in
/// docs/spec/05_Data_Models.md §13–17.
final class PayloadCodingTests: XCTestCase {
    private func encodeToObject(_ value: some Encodable) throws -> [String: Any] {
        let data = try JSONCoding.encoder.encode(value)
        return try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
    }

    func testBatteryPayloadShape() throws {
        let object = try encodeToObject(
            BatteryPayload(level: 84, charging: false, state: .unplugged, lowPowerMode: false)
        )
        XCTAssertEqual(object["level"] as? Int, 84)
        XCTAssertEqual(object["charging"] as? Bool, false)
        XCTAssertEqual(object["state"] as? String, "unplugged")
        XCTAssertEqual(object["low_power_mode"] as? Bool, false)
    }

    func testThermalPayloadShape() throws {
        let object = try encodeToObject(ThermalPayload(state: .nominal))
        XCTAssertEqual(object["state"] as? String, "nominal")
    }

    func testStoragePayloadShape() throws {
        let object = try encodeToObject(
            StoragePayload(totalBytes: 128_000_000_000, freeBytes: 42_000_000_000, usedBytes: 86_000_000_000, freePercent: 32.8)
        )
        XCTAssertEqual(object["total_bytes"] as? Int64, 128_000_000_000)
        XCTAssertEqual(object["free_bytes"] as? Int64, 42_000_000_000)
        XCTAssertEqual(object["used_bytes"] as? Int64, 86_000_000_000)
        XCTAssertEqual(object["free_percent"] as? Double, 32.8)
    }

    func testNetworkPayloadShape() throws {
        let object = try encodeToObject(
            NetworkPayload(reachable: true, interface: .wifi, expensive: false, constrained: false)
        )
        XCTAssertEqual(object["reachable"] as? Bool, true)
        XCTAssertEqual(object["interface"] as? String, "wifi")
        XCTAssertEqual(object["expensive"] as? Bool, false)
        XCTAssertEqual(object["constrained"] as? Bool, false)
    }

    func testNetworkInterfaceWiredEthernetRawValue() {
        XCTAssertEqual(NetworkInterface.wiredEthernet.rawValue, "wired_ethernet")
    }

    func testDevicePayloadShape() throws {
        let object = try encodeToObject(DevicePayload(
            deviceName: "Test iPhone",
            deviceModel: "iPhone15,2",
            systemName: "iOS",
            systemVersion: "17.5",
            locale: "en_GB",
            timezone: "Europe/London",
            screenWidth: 393,
            screenHeight: 852,
            screenScale: 3
        ))
        XCTAssertEqual(object["device_name"] as? String, "Test iPhone")
        XCTAssertEqual(object["device_model"] as? String, "iPhone15,2")
        XCTAssertEqual(object["system_name"] as? String, "iOS")
        XCTAssertEqual(object["system_version"] as? String, "17.5")
        XCTAssertEqual(object["screen_width"] as? Double, 393)
        XCTAssertEqual(object["screen_scale"] as? Double, 3)
    }

    func testThermalStateMappingCoversAllCases() {
        XCTAssertEqual(ThermalCollector.map(.nominal), .nominal)
        XCTAssertEqual(ThermalCollector.map(.fair), .fair)
        XCTAssertEqual(ThermalCollector.map(.serious), .serious)
        XCTAssertEqual(ThermalCollector.map(.critical), .critical)
    }
}
