"""Allow the agent to be started with: python -m sentinelx_agent"""

import sys

from sentinelx_agent.main import enroll_once, run_agent


if __name__ == "__main__":
    if "--enroll-only" in sys.argv:
        enroll_once()
    else:
        run_agent()
