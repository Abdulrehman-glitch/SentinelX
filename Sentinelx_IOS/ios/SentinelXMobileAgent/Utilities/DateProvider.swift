import Foundation

/// Injectable clock so time-dependent logic (token expiry, event timestamps)
/// stays deterministic in tests.
protocol DateProviding: Sendable {
    func now() -> Date
}

struct SystemDateProvider: DateProviding {
    func now() -> Date { Date() }
}
