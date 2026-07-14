import * as LocalAuthentication from "expo-local-authentication";

export interface BiometricCapability {
  available: boolean;
  enrolled: boolean;
  faceId: boolean;
  label: string;
}

export async function getBiometricCapability(): Promise<BiometricCapability> {
  const available = await LocalAuthentication.hasHardwareAsync();
  const enrolled = available && (await LocalAuthentication.isEnrolledAsync());
  let faceId = false;
  if (available) {
    const types = await LocalAuthentication.supportedAuthenticationTypesAsync();
    faceId = types.includes(LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION);
  }
  return {
    available,
    enrolled,
    faceId,
    label: faceId ? "Face ID" : "Touch ID",
  };
}

// Passcode fallback stays enabled so a failed scan never hard-locks the user out.
export async function authenticate(reason: string): Promise<boolean> {
  const result = await LocalAuthentication.authenticateAsync({
    promptMessage: reason,
    disableDeviceFallback: false,
    cancelLabel: "Cancel",
  });
  return result.success;
}
