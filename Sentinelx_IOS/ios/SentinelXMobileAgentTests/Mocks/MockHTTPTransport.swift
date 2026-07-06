import Foundation
@testable import SentinelXMobileAgent

/// Scripted transport: tests enqueue responses in the order the code under
/// test is expected to make requests, then assert on the recorded requests.
final class MockHTTPTransport: HTTPTransporting, @unchecked Sendable {
    struct Stub {
        let statusCode: Int
        let body: Data
        let headers: [String: String]

        init(statusCode: Int, json: String, headers: [String: String] = [:]) {
            self.statusCode = statusCode
            self.body = Data(json.utf8)
            self.headers = headers
        }
    }

    enum MockError: Error {
        case noStubbedResponse
    }

    private let lock = NSLock()
    private var stubs: [Stub] = []
    private(set) var requests: [URLRequest] = []

    func enqueue(_ stub: Stub) {
        lock.lock()
        defer { lock.unlock() }
        stubs.append(stub)
    }

    func execute(_ request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let stub: Stub? = lock.withLock {
            requests.append(request)
            return stubs.isEmpty ? nil : stubs.removeFirst()
        }

        guard let stub else { throw MockError.noStubbedResponse }
        let response = HTTPURLResponse(
            url: request.url ?? URL(string: "http://test.invalid")!,
            statusCode: stub.statusCode,
            httpVersion: "HTTP/1.1",
            headerFields: stub.headers
        )!
        return (stub.body, response)
    }

    var recordedPaths: [String] {
        lock.lock()
        defer { lock.unlock() }
        return requests.compactMap { $0.url?.path }
    }
}
