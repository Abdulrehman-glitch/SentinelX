import XCTest
@testable import SentinelXMobileAgent

final class TelemetryManagerTests: XCTestCase {
    private let now = Date(timeIntervalSince1970: 1_800_000_000)
    private let deviceId = "dev_TEST0001"

    private struct World {
        let manager: TelemetryManager
        let registry: CollectorRegistry
        let secretStore: DeviceSecretStore
    }

    private func makeWorld(registered: Bool = true) async throws -> World {
        let keychain = InMemoryKeychain()
        let secretStore = DeviceSecretStore(keychain: keychain)
        if registered {
            try await secretStore.save(DeviceIdentity(deviceId: deviceId, deviceSecret: "s"))
        }
        let tokenStore = TokenStore(keychain: keychain, dateProvider: FixedDateProvider(fixed: now))
        let apiClient = APIClient(
            environment: TestFixtures.environment(),
            transport: MockHTTPTransport(),
            tokenStore: tokenStore,
            deviceSecretStore: secretStore,
            dateProvider: FixedDateProvider(fixed: now)
        )
        let defaults = UserDefaults(suiteName: "TelemetryManagerTests-\(UUID().uuidString)")!
        let registry = CollectorRegistry()
        let manager = TelemetryManager(
            registry: registry,
            configurationService: ConfigurationService(apiClient: apiClient, defaults: defaults),
            deviceSecretStore: secretStore,
            environment: TestFixtures.environment(),
            dateProvider: FixedDateProvider(fixed: now)
        )
        return World(manager: manager, registry: registry, secretStore: secretStore)
    }

    func testStartPreparesConfiguresAndStartsEnabledCollectors() async throws {
        let world = try await makeWorld()
        let battery = MockCollector(id: "battery", category: .battery)
        let bluetooth = MockCollector(id: "bluetooth", category: .bluetooth)
        await world.registry.register(battery)
        await world.registry.register(bluetooth)

        await world.manager.start()

        let batteryStarts = await battery.startCount
        XCTAssertEqual(batteryStarts, 1)
        // Default config disables bluetooth — it must be configured but not
        // started.
        let bluetoothConfig = await bluetooth.appliedConfig
        XCTAssertEqual(bluetoothConfig?.enabled, false)
        let bluetoothStarts = await bluetooth.startCount
        XCTAssertEqual(bluetoothStarts, 0)
        let context = await battery.context
        XCTAssertEqual(context?.deviceId, deviceId)
    }

    func testStartWithoutIdentityDoesNothing() async throws {
        let world = try await makeWorld(registered: false)
        let battery = MockCollector(id: "battery", category: .battery)
        await world.registry.register(battery)

        await world.manager.start()

        let running = await world.manager.isRunning
        XCTAssertFalse(running)
        let starts = await battery.startCount
        XCTAssertEqual(starts, 0)
    }

    func testEmittedEventIsValidatedSequencedAndBuffered() async throws {
        let world = try await makeWorld()
        let battery = MockCollector(id: "battery", category: .battery)
        await world.registry.register(battery)
        await world.manager.start()

        await battery.emitSample(payload: .object(["level": .number(84)]))
        await battery.emitSample(payload: .object(["level": .number(83)]))

        let events = await world.manager.recentEvents()
        XCTAssertEqual(events.count, 2)
        XCTAssertEqual(events[0].sequence, 1)
        XCTAssertEqual(events[1].sequence, 2)
        XCTAssertEqual(events[0].deviceId, deviceId)
        XCTAssertEqual(events[0].metadata?.platform, .ios)
        let accepted = await world.manager.acceptedCount
        XCTAssertEqual(accepted, 2)
    }

    func testWrongDeviceIdEventIsRejected() async throws {
        let world = try await makeWorld()
        let battery = MockCollector(id: "battery", category: .battery)
        await world.registry.register(battery)
        await world.manager.start()

        let forged = TelemetryEvent(
            eventId: UUID(),
            deviceId: "dev_SOMEONE_ELSE",
            timestamp: now,
            category: .battery,
            type: "battery.snapshot",
            source: "test",
            sequence: nil,
            payload: .object([:]),
            metadata: nil
        )
        await battery.emitRaw(forged)

        let events = await world.manager.recentEvents()
        XCTAssertTrue(events.isEmpty)
        let rejected = await world.manager.rejectedCount
        XCTAssertEqual(rejected, 1)
    }

    func testEventStreamDeliversToSubscriber() async throws {
        let world = try await makeWorld()
        let battery = MockCollector(id: "battery", category: .battery)
        await world.registry.register(battery)
        await world.manager.start()

        let stream = await world.manager.eventStream()
        await battery.emitSample()

        var iterator = stream.makeAsyncIterator()
        let received = await iterator.next()
        XCTAssertEqual(received?.type, "battery.snapshot")
        XCTAssertEqual(received?.sequence, 1)
    }

    func testStopStopsCollectorsAndBlocksEmission() async throws {
        let world = try await makeWorld()
        let battery = MockCollector(id: "battery", category: .battery)
        await world.registry.register(battery)
        await world.manager.start()
        await world.manager.stop()

        let stops = await battery.stopCount
        XCTAssertEqual(stops, 1)

        await battery.emitSample()
        let events = await world.manager.recentEvents()
        XCTAssertTrue(events.isEmpty)
    }
}
