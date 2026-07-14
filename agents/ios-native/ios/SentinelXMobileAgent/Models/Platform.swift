import Foundation

enum Platform: String, Codable, Sendable {
    case ios
    case android
    case macos
    case windows
    case linux
    case raspberryPi = "raspberry_pi"
    case unknown
}
