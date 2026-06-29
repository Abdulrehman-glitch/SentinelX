import { Agentation } from "agentation";

export function AgentationDevTools() {
  if (!import.meta.env.DEV) {
    return null;
  }

  return <Agentation />;
}