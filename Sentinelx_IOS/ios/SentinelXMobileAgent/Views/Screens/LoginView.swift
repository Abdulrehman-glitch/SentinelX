import SwiftUI

struct LoginView: View {
    @StateObject private var viewModel: AuthViewModel

    init(viewModel: @autoclosure @escaping () -> AuthViewModel) {
        _viewModel = StateObject(wrappedValue: viewModel())
    }

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            VStack(spacing: 12) {
                Image(systemName: "shield.lefthalf.filled")
                    .font(.system(size: 52))
                    .foregroundStyle(.tint)
                Text("SentinelX Mobile Agent")
                    .font(.title2.bold())
                Text(subtitle)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }

            if let message = viewModel.errorMessage {
                Label(message, systemImage: "exclamationmark.triangle")
                    .font(.footnote)
                    .foregroundStyle(.red)
                    .multilineTextAlignment(.center)
            }

            actionArea

            Spacer()

            serverSection
        }
        .padding()
    }

    private var subtitle: String {
        switch viewModel.state {
        case .needsRegistration:
            "Register this iPhone with your SentinelX backend to start streaming telemetry."
        case .registered:
            "This device is registered. Connect to resume monitoring."
        case .authenticating:
            "Contacting server…"
        default:
            ""
        }
    }

    @ViewBuilder
    private var actionArea: some View {
        switch viewModel.state {
        case .authenticating:
            ProgressView()
                .controlSize(.large)
        case .needsRegistration:
            Button {
                Task { await viewModel.register() }
            } label: {
                Text("Register This Device")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
        case .registered:
            VStack(spacing: 12) {
                Button {
                    Task { await viewModel.connect() }
                } label: {
                    Text("Connect")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)

                Button("Forget this device", role: .destructive) {
                    Task { await viewModel.resetDeviceIdentity() }
                }
                .font(.footnote)
            }
        default:
            EmptyView()
        }
    }

    private var serverSection: some View {
        DisclosureGroup("Server") {
            VStack(alignment: .leading, spacing: 8) {
                TextField("http://192.168.1.10:8000/api/v1/mobile", text: $viewModel.serverAddress)
                    .textFieldStyle(.roundedBorder)
                    .keyboardType(.URL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                Button("Save") {
                    viewModel.saveServerAddress()
                }
                .buttonStyle(.bordered)
                if viewModel.serverAddressSaved {
                    Text("Saved — restart the app to apply.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .padding(.top, 8)
        }
        .font(.subheadline)
    }
}
