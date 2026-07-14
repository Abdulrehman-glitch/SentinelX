import Foundation

enum TelemetryCategory: String, Codable, Sendable, CaseIterable {
    case device
    case battery
    case thermal
    case storage
    case network
    case location
    case motion
    case activity
    case bluetooth
    case metrickit
    case diagnostic
    case alert
}
