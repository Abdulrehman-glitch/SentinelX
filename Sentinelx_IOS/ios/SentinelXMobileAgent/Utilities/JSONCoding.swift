import Foundation

/// Shared JSON coders for the mobile API contract: explicit CodingKeys for
/// snake_case mapping, ISO 8601 UTC timestamps (tolerant of fractional
/// seconds and "+00:00"-style offsets on input, always "Z" on output).
enum JSONCoding {
    static var encoder: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .custom { date, encoder in
            var container = encoder.singleValueContainer()
            try container.encode(ISO8601.string(from: date))
        }
        return encoder
    }

    static var decoder: JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let string = try container.decode(String.self)
            guard let date = ISO8601.date(from: string) else {
                throw DecodingError.dataCorruptedError(
                    in: container,
                    debugDescription: "Expected ISO 8601 date, got \(string)"
                )
            }
            return date
        }
        return decoder
    }
}

enum ISO8601 {
    static func date(from string: String) -> Date? {
        if let date = try? Date(string, strategy: .iso8601.includingFractionalSeconds(true)) {
            return date
        }
        if let date = try? Date(string, strategy: .iso8601) {
            return date
        }
        // Fallback covers offset variants ("+00:00") the format styles reject.
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: string) {
            return date
        }
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.date(from: string)
    }

    static func string(from date: Date) -> String {
        date.formatted(.iso8601.includingFractionalSeconds(true))
    }
}
