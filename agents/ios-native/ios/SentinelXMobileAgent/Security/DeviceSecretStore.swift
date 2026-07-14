import Foundation

struct DeviceIdentity: Codable, Equatable, Sendable {
    let deviceId: String
    let deviceSecret: String
}

/// Keychain-backed storage for the registration credentials. The device
/// secret is issued exactly once by the backend and never leaves the
/// Keychain except to authenticate a login call.
actor DeviceSecretStore {
    private enum Key {
        static let identity = "device.identity"
    }

    private let keychain: KeychainStoring
    private var cached: DeviceIdentity?
    private var loaded = false

    init(keychain: KeychainStoring) {
        self.keychain = keychain
    }

    func identity() -> DeviceIdentity? {
        if !loaded {
            loaded = true
            if let data = try? keychain.data(for: Key.identity) {
                cached = try? JSONCoding.decoder.decode(DeviceIdentity.self, from: data)
            }
        }
        return cached
    }

    func save(_ identity: DeviceIdentity) throws {
        let data = try JSONCoding.encoder.encode(identity)
        try keychain.set(data, for: Key.identity)
        cached = identity
        loaded = true
    }

    func clear() throws {
        try keychain.removeValue(for: Key.identity)
        cached = nil
        loaded = true
    }
}
