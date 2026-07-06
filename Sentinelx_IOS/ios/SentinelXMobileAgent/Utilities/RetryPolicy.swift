import Foundation

/// Exponential backoff with jitter, used by sync/reconnect logic.
struct RetryPolicy: Sendable {
    let baseDelay: TimeInterval
    let multiplier: Double
    let maxDelay: TimeInterval
    /// Attempts allowed before giving up; nil means retry forever.
    let maxAttempts: Int?

    static let upload = RetryPolicy(baseDelay: 2, multiplier: 2, maxDelay: 300, maxAttempts: 8)
    static let reconnect = RetryPolicy(baseDelay: 1, multiplier: 2, maxDelay: 60, maxAttempts: nil)

    /// Deterministic delay for a 1-based attempt number, nil once attempts
    /// are exhausted.
    func delay(forAttempt attempt: Int) -> TimeInterval? {
        guard attempt >= 1 else { return nil }
        if let maxAttempts, attempt > maxAttempts { return nil }
        let raw = baseDelay * pow(multiplier, Double(attempt - 1))
        return min(raw, maxDelay)
    }

    /// Adds ±20% jitter so a fleet of devices doesn't reconnect in lockstep.
    func jitteredDelay(
        forAttempt attempt: Int,
        using generator: inout some RandomNumberGenerator
    ) -> TimeInterval? {
        guard let base = delay(forAttempt: attempt) else { return nil }
        return base * Double.random(in: 0.8...1.2, using: &generator)
    }
}
