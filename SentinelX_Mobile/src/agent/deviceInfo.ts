import * as Application from "expo-application";
import * as Battery from "expo-battery";
import * as Device from "expo-device";
import { Paths } from "expo-file-system";
import { getLocales, getCalendars } from "expo-localization";
import * as Network from "expo-network";
import * as Notifications from "expo-notifications";
import { Dimensions, PixelRatio, Platform } from "react-native";

import { AGENT_VERSION } from "@/lib/config";

// §6 — only public, approved APIs. No process lists, no other apps' data.
export interface DeviceSnapshot {
  category: string;
  model: string | null;
  osName: string;
  osVersion: string;
  appVersion: string | null;
  buildNumber: string | null;
  agentVersion: string;
  locale: string | null;
  region: string | null;
  timezone: string | null;
  screenWidth: number;
  screenHeight: number;
  screenScale: number;
  batteryLevel: number | null;
  batteryState: string;
  lowPowerMode: boolean;
  connectionType: string;
  isConnected: boolean;
  ipAddress: string | null;
  totalDiskBytes: number | null;
  availableDiskBytes: number | null;
  notificationPermission: string;
}

function batteryStateLabel(state: Battery.BatteryState): string {
  switch (state) {
    case Battery.BatteryState.CHARGING:
      return "charging";
    case Battery.BatteryState.FULL:
      return "full";
    case Battery.BatteryState.UNPLUGGED:
      return "unplugged";
    default:
      return "unknown";
  }
}

export async function collectDeviceSnapshot(): Promise<DeviceSnapshot> {
  const [batteryLevel, batteryState, lowPower, network, ip, notifPerm] = await Promise.all([
    Battery.getBatteryLevelAsync().catch(() => -1),
    Battery.getBatteryStateAsync().catch(() => Battery.BatteryState.UNKNOWN),
    Battery.isLowPowerModeEnabledAsync().catch(() => false),
    Network.getNetworkStateAsync().catch(() => null),
    Network.getIpAddressAsync().catch(() => null),
    Notifications.getPermissionsAsync().catch(() => null),
  ]);

  let totalDisk: number | null = null;
  let availableDisk: number | null = null;
  try {
    totalDisk = Paths.totalDiskSpace;
    availableDisk = Paths.availableDiskSpace;
  } catch {
    // not available on all platforms
  }

  const { width, height } = Dimensions.get("screen");
  const locales = getLocales();
  const calendars = getCalendars();

  return {
    category: Device.deviceType === Device.DeviceType.TABLET ? "tablet" : "phone",
    model: Device.modelName,
    osName: Device.osName ?? Platform.OS,
    osVersion: Device.osVersion ?? "unknown",
    appVersion: Application.nativeApplicationVersion,
    buildNumber: Application.nativeBuildVersion,
    agentVersion: AGENT_VERSION,
    locale: locales[0]?.languageTag ?? null,
    region: locales[0]?.regionCode ?? null,
    timezone: calendars[0]?.timeZone ?? null,
    screenWidth: Math.round(width),
    screenHeight: Math.round(height),
    screenScale: PixelRatio.get(),
    batteryLevel: batteryLevel >= 0 ? Math.round(batteryLevel * 100) : null,
    batteryState: batteryStateLabel(batteryState),
    lowPowerMode: lowPower,
    connectionType: network?.type?.toLowerCase() ?? "unknown",
    isConnected: network?.isConnected ?? false,
    ipAddress: ip && ip !== "0.0.0.0" ? ip : null,
    notificationPermission: notifPerm?.status ?? "unknown",
  };
}

// Compact state summary carried in the heartbeat message (≤500 chars server-side).
export function heartbeatMessage(snapshot: DeviceSnapshot): string {
  const parts = [
    snapshot.batteryLevel != null ? `battery ${snapshot.batteryLevel}%` : null,
    snapshot.batteryState !== "unknown" ? snapshot.batteryState : null,
    snapshot.lowPowerMode ? "low-power" : null,
    `net ${snapshot.connectionType}`,
    `agent v${snapshot.agentVersion}`,
  ].filter(Boolean);
  return parts.join(" · ").slice(0, 500);
}
