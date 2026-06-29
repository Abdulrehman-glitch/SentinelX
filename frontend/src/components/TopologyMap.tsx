import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import { Link } from "react-router";
import { Badge } from "./Badge";
import type { Alert, Device, Incident, RecoveryAction } from "../types/api";

type TopologyMapProps = {
  devices: Device[];
  alerts: Alert[];
  incidents: Incident[];
  recoveryActions: RecoveryAction[];
};

function getDeviceId(device: Device) {
  return device.id ?? device.device_id ?? "";
}

function isAlertResolved(alert: Alert) {
  return alert.resolved ?? alert.is_resolved ?? false;
}

function getNodeStyle(kind: "platform" | "healthy" | "warning" | "critical" | "info") {
  const baseStyle = {
    borderRadius: 14,
    border: "1px solid rgba(255,255,255,0.12)",
    color: "#f8fafc",
    padding: 12,
    width: 190,
    fontSize: 12,
    fontWeight: 700,
  };

  if (kind === "platform") {
    return {
      ...baseStyle,
      background: "linear-gradient(135deg, rgba(245,158,11,0.35), rgba(15,23,42,0.95))",
      border: "1px solid rgba(245,158,11,0.45)",
    };
  }

  if (kind === "critical") {
    return {
      ...baseStyle,
      background: "rgba(127,29,29,0.72)",
      border: "1px solid rgba(244,63,94,0.42)",
    };
  }

  if (kind === "warning") {
    return {
      ...baseStyle,
      background: "rgba(120,53,15,0.72)",
      border: "1px solid rgba(245,158,11,0.42)",
    };
  }

  if (kind === "healthy") {
    return {
      ...baseStyle,
      background: "rgba(20,83,45,0.65)",
      border: "1px solid rgba(34,197,94,0.36)",
    };
  }

  return {
    ...baseStyle,
    background: "rgba(15,23,42,0.88)",
  };
}

function getDeviceRisk(device: Device, alerts: Alert[]) {
  const deviceId = getDeviceId(device);
  const deviceAlerts = alerts.filter((alert) => alert.device_id === deviceId);

  if (device.status?.toLowerCase() === "offline") {
    return "critical" as const;
  }

  if (
    deviceAlerts.some(
      (alert) =>
        !isAlertResolved(alert) && alert.severity.toLowerCase() === "critical",
    )
  ) {
    return "critical" as const;
  }

  if (
    deviceAlerts.some(
      (alert) =>
        !isAlertResolved(alert) && alert.severity.toLowerCase() === "warning",
    )
  ) {
    return "warning" as const;
  }

  return "healthy" as const;
}

function buildTopology(
  devices: Device[],
  alerts: Alert[],
  incidents: Incident[],
  recoveryActions: RecoveryAction[],
) {
  const nodes: Node[] = [
    {
      id: "sentinelx-platform",
      position: { x: 0, y: 180 },
      data: {
        label: (
          <div>
            <p>SentinelX Platform</p>
            <p style={{ marginTop: 4, color: "#fbbf24", fontSize: 11 }}>
              Monitoring Core
            </p>
          </div>
        ),
      },
      style: getNodeStyle("platform"),
    },
  ];

  const edges: Edge[] = [];

  devices.forEach((device, index) => {
    const deviceId = getDeviceId(device);
    const risk = getDeviceRisk(device, alerts);

    const x = 300;
    const y = index * 150;

    nodes.push({
      id: `device-${deviceId}`,
      position: { x, y },
      data: {
        label: (
          <div>
            <p>{device.hostname}</p>
            <p style={{ marginTop: 4, color: "#94a3b8", fontSize: 11 }}>
              {device.status ?? "unknown"} · {device.os_name}
            </p>
          </div>
        ),
      },
      style: getNodeStyle(risk),
    });

    edges.push({
      id: `edge-platform-${deviceId}`,
      source: "sentinelx-platform",
      target: `device-${deviceId}`,
      animated: risk !== "healthy",
      style: {
        stroke: risk === "critical" ? "#f43f5e" : risk === "warning" ? "#f59e0b" : "#22c55e",
      },
    });

    const deviceAlerts = alerts
      .filter((alert) => alert.device_id === deviceId)
      .slice(0, 2);

    deviceAlerts.forEach((alert, alertIndex) => {
      const alertNodeId = `alert-${deviceId}-${alertIndex}`;

      nodes.push({
        id: alertNodeId,
        position: { x: 590, y: y + alertIndex * 78 },
        data: {
          label: (
            <div>
              <p>{alert.severity.toUpperCase()} Alert</p>
              <p style={{ marginTop: 4, color: "#cbd5e1", fontSize: 10 }}>
                {alert.message.slice(0, 42)}
                {alert.message.length > 42 ? "..." : ""}
              </p>
            </div>
          ),
        },
        style: getNodeStyle(alert.severity.toLowerCase() === "critical" ? "critical" : "warning"),
      });

      edges.push({
        id: `edge-${deviceId}-${alertNodeId}`,
        source: `device-${deviceId}`,
        target: alertNodeId,
        animated: !isAlertResolved(alert),
        style: {
          stroke: alert.severity.toLowerCase() === "critical" ? "#f43f5e" : "#f59e0b",
        },
      });
    });
  });

  incidents.slice(0, 4).forEach((incident, index) => {
    nodes.push({
      id: `incident-${incident.id}`,
      position: { x: 890, y: index * 120 },
      data: {
        label: (
          <div>
            <p>{incident.title}</p>
            <p style={{ marginTop: 4, color: "#94a3b8", fontSize: 11 }}>
              {incident.status}
            </p>
          </div>
        ),
      },
      style: getNodeStyle(
        incident.status === "resolved"
          ? "healthy"
          : incident.severity === "critical"
            ? "critical"
            : "warning",
      ),
    });

    if (incident.device_id) {
      edges.push({
        id: `edge-incident-${incident.id}`,
        source: `device-${incident.device_id}`,
        target: `incident-${incident.id}`,
        animated: incident.status !== "resolved",
        style: { stroke: "#f59e0b" },
      });
    }
  });

  recoveryActions.slice(0, 4).forEach((action, index) => {
    nodes.push({
      id: `recovery-${action.id ?? action.recovery_action_id ?? index}`,
      position: { x: 890, y: 520 + index * 100 },
      data: {
        label: (
          <div>
            <p>{action.action_type}</p>
            <p style={{ marginTop: 4, color: "#94a3b8", fontSize: 11 }}>
              {action.status}
            </p>
          </div>
        ),
      },
      style: getNodeStyle("info"),
    });

    if (action.device_id) {
      edges.push({
        id: `edge-recovery-${index}`,
        source: `device-${action.device_id}`,
        target: `recovery-${action.id ?? action.recovery_action_id ?? index}`,
        style: { stroke: "#38bdf8" },
      });
    }
  });

  return { nodes, edges };
}

export function TopologyMap({
  devices,
  alerts,
  incidents,
  recoveryActions,
}: TopologyMapProps) {
  const { nodes, edges } = buildTopology(
    devices,
    alerts,
    incidents,
    recoveryActions,
  );

  const criticalDevices = devices.filter(
    (device) => getDeviceRisk(device, alerts) === "critical",
  );

  const warningDevices = devices.filter(
    (device) => getDeviceRisk(device, alerts) === "warning",
  );

  return (
    <>
      <section className="sx-panel rounded-2xl p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-50">
              Infrastructure Topology
            </h2>

            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">
              Relationship map between the SentinelX platform, monitored
              devices, alerts, incidents, and logged recovery actions.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge tone="red">{criticalDevices.length} critical</Badge>
            <Badge tone="amber">{warningDevices.length} warning</Badge>
            <Badge tone="green">{devices.length} devices</Badge>
          </div>
        </div>
      </section>

      <section className="sx-panel mt-8 h-[720px] rounded-2xl p-3">
        <ReactFlow nodes={nodes} edges={edges} fitView>
          <Background color="rgba(255,255,255,0.08)" gap={24} />
          <Controls />
          <MiniMap
            nodeColor={(node) => {
              if (String(node.id).startsWith("alert")) {
                return "#f59e0b";
              }

              if (String(node.id).startsWith("incident")) {
                return "#f43f5e";
              }

              if (String(node.id).startsWith("device")) {
                return "#22c55e";
              }

              return "#f59e0b";
            }}
          />
        </ReactFlow>
      </section>

      <section className="mt-8 grid gap-4 md:grid-cols-3">
        <Link to="/devices" className="sx-panel rounded-2xl p-5 transition hover:border-amber-400/30">
          <p className="text-sm font-semibold text-slate-400">Device Registry</p>
          <p className="mt-2 text-2xl font-bold text-slate-50">{devices.length}</p>
        </Link>

        <Link to="/alerts" className="sx-panel rounded-2xl p-5 transition hover:border-amber-400/30">
          <p className="text-sm font-semibold text-slate-400">Alert Signals</p>
          <p className="mt-2 text-2xl font-bold text-slate-50">{alerts.length}</p>
        </Link>

        <Link to="/incidents" className="sx-panel rounded-2xl p-5 transition hover:border-amber-400/30">
          <p className="text-sm font-semibold text-slate-400">Incident Links</p>
          <p className="mt-2 text-2xl font-bold text-slate-50">{incidents.length}</p>
        </Link>
      </section>
    </>
  );
}