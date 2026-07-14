import { sentinelxApi } from "@/api/endpoints";
import { buildError } from "@/lib/errors";
import { can } from "@/lib/roles";
import type { UserPublic } from "@/api/types";
import { collectDeviceSnapshot } from "./deviceInfo";
import {
  AgentEnrolment,
  clearEnrolment,
  getOrCreateAgentId,
  loadEnrolment,
  saveEnrolment,
} from "./identity";

export interface EnrolmentProposal {
  agentId: string;
  displayName: string;
  orgSlug: string;
  model: string | null;
  osVersion: string;
}

// §5 — show the proposed device identity before anything is registered.
export async function buildProposal(orgSlug: string): Promise<EnrolmentProposal> {
  const agentId = await getOrCreateAgentId();
  const snapshot = await collectDeviceSnapshot();
  return {
    agentId,
    displayName: snapshot.model ? `${snapshot.model} (SentinelX Agent)` : agentId,
    orgSlug,
    model: snapshot.model,
    osVersion: `${snapshot.osName} ${snapshot.osVersion}`,
  };
}

// Registers the iPhone as a Device row, then provisions a device credential.
// Admin+ users self-provision; others must paste an admin-issued token.
export async function enrolAgent(opts: {
  user: UserPublic;
  orgSlug: string;
  displayName: string;
  manualToken?: string;
}): Promise<AgentEnrolment> {
  const agentId = await getOrCreateAgentId();
  const snapshot = await collectDeviceSnapshot();

  const device = await sentinelxApi.registerDevice({
    hostname: agentId,
    display_name: opts.displayName,
    ip_address: snapshot.ipAddress,
    os_name: `${snapshot.osName} ${snapshot.osVersion}`,
    organization_slug: opts.orgSlug,
    device_type: "mobile",
    agent_type: "ios_mobile_agent",
    agent_version: snapshot.agentVersion,
  });

  let deviceToken: string;
  let credentialId: string | null = null;

  if (opts.manualToken?.trim()) {
    deviceToken = opts.manualToken.trim();
  } else if (can.selfProvisionAgent(opts.user.role)) {
    const credential = await sentinelxApi.createDeviceCredential(
      device.id,
      `${opts.displayName} agent token`,
    );
    deviceToken = credential.token;
    credentialId = credential.id;
  } else {
    throw buildError("permission_denied", {
      detail: "Your role cannot create device credentials. Ask an administrator for an agent token.",
    });
  }

  const enrolment: AgentEnrolment = {
    agentId,
    deviceId: device.id,
    deviceToken,
    credentialId,
    enrolledAt: new Date().toISOString(),
    orgSlug: opts.orgSlug,
    displayName: opts.displayName,
  };
  await saveEnrolment(enrolment);
  return enrolment;
}

// §5 — rotate: issue a fresh credential, then revoke the old one.
export async function rotateCredential(user: UserPublic): Promise<AgentEnrolment> {
  const current = await loadEnrolment();
  if (!current) throw buildError("device_token_invalid");
  if (!can.manageCredentials(user.role)) {
    throw buildError("permission_denied");
  }
  const fresh = await sentinelxApi.createDeviceCredential(
    current.deviceId,
    `${current.displayName} agent token (rotated)`,
  );
  if (current.credentialId) {
    await sentinelxApi.revokeDeviceCredential(current.credentialId).catch(() => {});
  }
  const updated: AgentEnrolment = {
    ...current,
    deviceToken: fresh.token,
    credentialId: fresh.id,
  };
  await saveEnrolment(updated);
  return updated;
}

export async function removeAgent(opts: { revokeCredential: boolean }): Promise<void> {
  const current = await loadEnrolment();
  if (current?.credentialId && opts.revokeCredential) {
    await sentinelxApi.revokeDeviceCredential(current.credentialId).catch(() => {});
  }
  await clearEnrolment();
}
