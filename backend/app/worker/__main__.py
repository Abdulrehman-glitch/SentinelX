"""Entry point: python -m app.worker

Runs one worker in the foreground. Scale by starting more processes; they
coordinate through the queue itself and need no configuration to do so.
"""

import argparse
import logging

from app.core.logging_config import configure_logging
from app.worker.runner import Worker, install_signal_handlers


def main() -> None:
    parser = argparse.ArgumentParser(description="SentinelX background worker")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--lease-seconds", type=int, default=120)
    parser.add_argument("--idle-sleep", type=float, default=2.0)
    parser.add_argument(
        "--once",
        action="store_true",
        help="Drain one batch and exit, instead of running until stopped.",
    )
    args = parser.parse_args()

    configure_logging()
    logging.getLogger("sentinelx.worker").setLevel(logging.INFO)

    worker = Worker(
        batch_size=args.batch_size,
        lease_seconds=args.lease_seconds,
        idle_sleep_seconds=args.idle_sleep,
    )

    if args.once:
        handled = worker.run_once()
        print(f"processed {handled} job(s)")
        return

    install_signal_handlers(worker)
    worker.run_forever()


if __name__ == "__main__":
    main()
