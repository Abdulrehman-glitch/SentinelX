import * as Crypto from "expo-crypto";
import * as SecureStore from "expo-secure-store";

// Agent identity + device credential live in the Keychain. The agent id is a
// stable installation identifier: it survives sign-out but not reinstall.
const KEYS = {
  agentId: "sx.agent.id",
  deviceId: "sx.agent.deviceId",
  deviceToken: "sx.agent.deviceToken",
  credentialId: "sx.agent.credentialId",
  enrolledAt: "sx.agent.enrolledAt",
  orgSlug: "sx.agent.orgSlug",
  displayName: "sx.agent.displayName",
} as const;

export interface AgentEnrolment {
  agentId: string;
  deviceId: string;
  deviceToken: string;
  credentialId: string | null;
  enrolledAt: string;
  orgSlug: string;
  displayName: string;
}

export async function getOrCreateAgentId(): Promise<string> {
  const existing = await SecureStore.getItemAsync(KEYS.agentId);
  if (existing) return existing;
  const id = `iphone-agent-${Crypto.randomUUID().slice(0, 8)}`;
  await SecureStore.setItemAsync(KEYS.agentId, id);
  return id;
}

export async function saveEnrolment(enrolment: AgentEnrolment): Promise<void> {
  await SecureStore.setItemAsync(KEYS.agentId, enrolment.agentId);
  await SecureStore.setItemAsync(KEYS.deviceId, enrolment.deviceId);
  await SecureStore.setItemAsync(KEYS.deviceToken, enrolment.deviceToken);
  await SecureStore.setItemAsync(KEYS.credentialId, enrolment.credentialId ?? "");
  await SecureStore.setItemAsync(KEYS.enrolledAt, enrolment.enrolledAt);
  await SecureStore.setItemAsync(KEYS.orgSlug, enrolment.orgSlug);
  await SecureStore.setItemAsync(KEYS.displayName, enrolment.displayName);
}

export async function loadEnrolment(): Promise<AgentEnrolment | null> {
  const [agentId, deviceId, deviceToken, credentialId, enrolledAt, orgSlug, displayName] =
    await Promise.all([
      SecureStore.getItemAsync(KEYS.agentId),
      SecureStore.getItemAsync(KEYS.deviceId),
      SecureStore.getItemAsync(KEYS.deviceToken),
      SecureStore.getItemAsync(KEYS.credentialId),
      SecureStore.getItemAsync(KEYS.enrolledAt),
      SecureStore.getItemAsync(KEYS.orgSlug),
      SecureStore.getItemAsync(KEYS.displayName),
    ]);
  if (!agentId || !deviceId || !deviceToken) return null;
  return {
    agentId,
    deviceId,
    deviceToken,
    credentialId: credentialId || null,
    enrolledAt: enrolledAt ?? new Date().toISOString(),
    orgSlug: orgSlug ?? "",
    displayName: displayName ?? agentId,
  };
}

export async function clearEnrolment(): Promise<void> {
  // Keep the agent id so a re-enrolled install maps back to the same device row.
  await SecureStore.deleteItemAsync(KEYS.deviceId);
  await SecureStore.deleteItemAsync(KEYS.deviceToken);
  await SecureStore.deleteItemAsync(KEYS.credentialId);
  await SecureStore.deleteItemAsync(KEYS.enrolledAt);
  await SecureStore.deleteItemAsync(KEYS.orgSlug);
  await SecureStore.deleteItemAsync(KEYS.displayName);
}
