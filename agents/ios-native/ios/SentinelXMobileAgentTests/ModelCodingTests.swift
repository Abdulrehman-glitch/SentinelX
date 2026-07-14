import XCTest
@testable import SentinelXMobileAgent

final class ModelCodingTests: XCTestCase {
    func testRegistrationRequestEncodesSnakeCase() throws {
        let request = DeviceRegistrationRequest(
            platform: .ios,
            deviceName: "Test iPhone",
            deviceModel: "iPhone15,2",
            osVersion: "iOS 17.5",
            appVersion: "1.0.0",
            vendorIdentifier: "vendor-id",
            timezone: "Europe/London",
            locale: "en_GB"
        )

        let data = try JSONCoding.encoder.encode(request)
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])

        XCTAssertEqual(object["platform"] as? String, "ios")
        XCTAssertEqual(object["device_name"] as? String, "Test iPhone")
        XCTAssertEqual(object["device_model"] as? String, "iPhone15,2")
        XCTAssertEqual(object["os_version"] as? String, "iOS 17.5")
        XCTAssertEqual(object["app_version"] as? String, "1.0.0")
        XCTAssertEqual(object["vendor_identifier"] as? String, "vendor-id")
        XCTAssertEqual(object["timezone"] as? String, "Europe/London")
        XCTAssertEqual(object["locale"] as? String, "en_GB")
    }

    func testRegistrationResponseDecodes() throws {
        let response = try JSONCoding.decoder.decode(
            DeviceRegistrationResponse.self,
            from: Data(TestFixtures.registrationResponseJSON.utf8)
        )
        XCTAssertEqual(response.deviceId, "dev_TEST0001")
        XCTAssertEqual(response.deviceSecret, "test-secret-value")
        XCTAssertEqual(response.status, .active)
    }

    func testTokenResponseDecodes() throws {
        let response = try JSONCoding.decoder.decode(
            TokenResponse.self,
            from: Data(TestFixtures.tokenResponseJSON.utf8)
        )
        XCTAssertEqual(response.accessToken, "test-access-token")
        XCTAssertEqual(response.refreshToken, "test-refresh-token")
        XCTAssertEqual(response.tokenType, "bearer")
        XCTAssertEqual(response.expiresIn, 1800)
    }

    func testProfileDecodesBothDateVariants() throws {
        // registered_at uses plain Z, last_seen uses fractional seconds with
        // a +00:00 offset — both must parse.
        let profile = try JSONCoding.decoder.decode(
            DeviceProfile.self,
            from: Data(TestFixtures.profileJSON.utf8)
        )
        XCTAssertEqual(profile.deviceId, "dev_TEST0001")
        XCTAssertNotNil(profile.registeredAt)
        XCTAssertNotNil(profile.lastSeen)
    }

    func testISO8601RoundTrip() throws {
        let date = try XCTUnwrap(ISO8601.date(from: "2026-07-06T12:00:00Z"))
        let string = ISO8601.string(from: date)
        XCTAssertEqual(ISO8601.date(from: string), date)
    }

    func testJSONValueRoundTrip() throws {
        let value: JSONValue = .object([
            "level": .number(84),
            "charging": .bool(false),
            "state": .string("unplugged"),
            "tags": .array([.string("a"), .number(1), .null]),
            "nested": .object(["x": .number(0.5)]),
        ])

        let data = try JSONCoding.encoder.encode(value)
        let decoded = try JSONCoding.decoder.decode(JSONValue.self, from: data)
        XCTAssertEqual(decoded, value)
        XCTAssertEqual(decoded["level"]?.intValue, 84)
        XCTAssertEqual(decoded["charging"]?.boolValue, false)
        XCTAssertEqual(decoded["nested"]?["x"]?.numberValue, 0.5)
    }

    func testJSONValueFromEncodable() throws {
        struct Sample: Encodable {
            let batteryLevel: Int
            enum CodingKeys: String, CodingKey {
                case batteryLevel = "battery_level"
            }
        }
        let value = try JSONValue(encoding: Sample(batteryLevel: 42))
        XCTAssertEqual(value["battery_level"]?.intValue, 42)
    }
}
