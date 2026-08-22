"""SentinelX background worker.

Run with: python -m app.worker
"""

from app.worker.runner import Worker, install_signal_handlers

__all__ = ["Worker", "install_signal_handlers"]
