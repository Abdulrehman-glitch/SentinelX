import XCTest
@testable import SentinelXMobileAgent

final class RetryPolicyTests: XCTestCase {
    func testExponentialGrowth() {
        let policy = RetryPolicy(baseDelay: 2, multiplier: 2, maxDelay: 300, maxAttempts: 8)
        XCTAssertEqual(policy.delay(forAttempt: 1), 2)
        XCTAssertEqual(policy.delay(forAttempt: 2), 4)
        XCTAssertEqual(policy.delay(forAttempt: 3), 8)
        XCTAssertEqual(policy.delay(forAttempt: 4), 16)
    }

    func testDelayIsCapped() {
        let policy = RetryPolicy(baseDelay: 2, multiplier: 2, maxDelay: 300, maxAttempts: nil)
        XCTAssertEqual(policy.delay(forAttempt: 12), 300)
    }

    func testExhaustedAttemptsReturnNil() {
        let policy = RetryPolicy(baseDelay: 1, multiplier: 2, maxDelay: 60, maxAttempts: 3)
        XCTAssertNotNil(policy.delay(forAttempt: 3))
        XCTAssertNil(policy.delay(forAttempt: 4))
        XCTAssertNil(policy.delay(forAttempt: 0))
    }

    func testJitterStaysWithinBounds() {
        let policy = RetryPolicy(baseDelay: 10, multiplier: 2, maxDelay: 300, maxAttempts: nil)
        var generator = SeededRandomNumberGenerator(seed: 42)
        for attempt in 1...5 {
            let base = policy.delay(forAttempt: attempt)!
            let jittered = policy.jitteredDelay(forAttempt: attempt, using: &generator)!
            XCTAssertGreaterThanOrEqual(jittered, base * 0.8)
            XCTAssertLessThanOrEqual(jittered, base * 1.2)
        }
    }

    func testInfiniteRetriesWhenMaxAttemptsNil() {
        let policy = RetryPolicy.reconnect
        XCTAssertNotNil(policy.delay(forAttempt: 1000))
    }
}
