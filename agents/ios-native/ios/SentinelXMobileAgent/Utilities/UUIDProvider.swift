import Foundation

/// Injectable UUID source for deterministic tests of event/request IDs.
protocol UUIDProviding: Sendable {
    func uuid() -> UUID
}

struct SystemUUIDProvider: UUIDProviding {
    func uuid() -> UUID { UUID() }
}
