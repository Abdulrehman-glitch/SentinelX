import XCTest
@testable import SentinelXMobileAgent

final class TelemetryEventValidatorTests: XCTestCase {
    private let now = Date(timeIntervalSince1970: 1_800_000_000)
    private let deviceId = "dev_TEST0001"

    private func makeEvent(
        deviceId: String = "dev_TEST0001",
        timestamp: Date? = nil,
        type: String = "battery.snapshot",
        source: String = "ios.uidevice",
        payload: JSONValue = .object(["level": .number(84)])
    ) -> TelemetryEvent {
        TelemetryEvent(
            eventId: UUID(),
            deviceId: deviceId,
            timestamp: timestamp ?? now,
            category: .battery,
            type: type,
            source: source,
            sequence: nil,
            payload: payload,
            metadata: nil
        )
    }

    func testValidEventPasses() {
        let result = TelemetryEventValidator.validate(makeEvent(), expectedDeviceId: deviceId, now: now)
        XCTAssertNil(result)
    }

    func testDeviceIdMismatchFails() {
        let result = TelemetryEventValidator.validate(
            makeEvent(deviceId: "dev_OTHER"),
            expectedDeviceId: deviceId,
            now: now
        )
        XCTAssertEqual(result, .deviceIdMismatch)
    }

    func testNonObjectPayloadFails() {
        let result = TelemetryEventValidator.validate(
            makeEvent(payload: .number(42)),
            expectedDeviceId: deviceId,
            now: now
        )
        XCTAssertEqual(result, .payloadNotObject)
    }

    func testEmptyTypeAndSourceFail() {
        XCTAssertEqual(
            TelemetryEventValidator.validate(makeEvent(type: ""), expectedDeviceId: deviceId, now: now),
            .emptyType
        )
        XCTAssertEqual(
            TelemetryEventValidator.validate(makeEvent(source: ""), expectedDeviceId: deviceId, now: now),
            .emptySource
        )
    }

    func testFarFutureTimestampFails() {
        let result = TelemetryEventValidator.validate(
            makeEvent(timestamp: now.addingTimeInterval(600)),
            expectedDeviceId: deviceId,
            now: now
        )
        XCTAssertEqual(result, .timestampTooFarInFuture)
    }

    func testSmallClockDriftIsTolerated() {
        let result = TelemetryEventValidator.validate(
            makeEvent(timestamp: now.addingTimeInterval(60)),
            expectedDeviceId: deviceId,
            now: now
        )
        XCTAssertNil(result)
    }
}
