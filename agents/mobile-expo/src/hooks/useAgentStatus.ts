import { useEffect, useState } from "react";

import { agentRuntime, AgentStatus } from "@/agent/heartbeat";

export function useAgentStatus(): AgentStatus {
  const [status, setStatus] = useState<AgentStatus>(agentRuntime.getStatus());
  useEffect(() => agentRuntime.subscribe(setStatus), []);
  return status;
}
