import * as Network from "expo-network";
import { useEffect, useState } from "react";

interface NetworkStatus {
  online: boolean;
  type: string;
}

export function useNetworkStatus(): NetworkStatus {
  const [status, setStatus] = useState<NetworkStatus>({ online: true, type: "unknown" });

  useEffect(() => {
    let mounted = true;
    Network.getNetworkStateAsync()
      .then((state) => {
        if (mounted) setStatus({ online: state.isConnected ?? false, type: state.type?.toLowerCase() ?? "unknown" });
      })
      .catch(() => {});
    const sub = Network.addNetworkStateListener((state) => {
      if (mounted) setStatus({ online: state.isConnected ?? false, type: state.type?.toLowerCase() ?? "unknown" });
    });
    return () => {
      mounted = false;
      sub.remove();
    };
  }, []);

  return status;
}
