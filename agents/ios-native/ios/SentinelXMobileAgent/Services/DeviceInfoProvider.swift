import UIKit

struct DeviceInfoSnapshot: Sendable, Equatable {
    let deviceName: String
    let deviceModel: String
    let systemName: String
    let systemVersion: String
    let localeIdentifier: String
    let timezoneIdentifier: String
    let vendorIdentifier: String
    let screenWidth: Double
    let screenHeight: Double
    let screenScale: Double
}

/// Isolates UIKit device queries so services and collectors stay testable.
protocol DeviceInfoProviding: Sendable {
    @MainActor func snapshot() -> DeviceInfoSnapshot
}

struct UIKitDeviceInfoProvider: DeviceInfoProviding {
    @MainActor
    func snapshot() -> DeviceInfoSnapshot {
        let device = UIDevice.current
        let screen = UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .first?
            .screen
        let bounds = screen?.bounds.size ?? .zero

        return DeviceInfoSnapshot(
            deviceName: device.name,
            deviceModel: Self.hardwareModel(),
            systemName: device.systemName,
            systemVersion: device.systemVersion,
            localeIdentifier: Locale.current.identifier,
            timezoneIdentifier: TimeZone.current.identifier,
            vendorIdentifier: device.identifierForVendor?.uuidString ?? "unavailable",
            screenWidth: bounds.width,
            screenHeight: bounds.height,
            screenScale: screen.map { Double($0.scale) } ?? 0
        )
    }

    /// Hardware identifier like "iPhone15,2" via uname — public API; the
    /// UIDevice.model string only says "iPhone".
    private static func hardwareModel() -> String {
        var systemInfo = utsname()
        uname(&systemInfo)
        return withUnsafeBytes(of: &systemInfo.machine) { buffer in
            String(decoding: buffer.prefix(while: { $0 != 0 }), as: UTF8.self)
        }
    }
}
