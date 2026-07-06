import SwiftUI

struct RootView: View {
    @EnvironmentObject private var container: AppContainer

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "shield.lefthalf.filled")
                .font(.system(size: 44))
                .foregroundStyle(.tint)
            Text("SentinelX Mobile Agent")
                .font(.title2.bold())
            Text("Phase 0 — project bootstrap")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
    }
}
