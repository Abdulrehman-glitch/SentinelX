"""Shared configuration for SentinelX embedded bridge scripts."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SENTINELX_",
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # SentinelX backend
    api_base_url: str = Field("http://127.0.0.1:8000/api/v1")
    device_token: str = Field(...)               # bearer token for the Arduino device
    device_id: str = Field(...)                   # UUID of the device record in SentinelX

    # Serial bridge
    serial_port: str = Field("COM3")              # e.g. COM3 on Windows, /dev/ttyACM0 on Linux
    serial_baud: int = Field(115200)
    serial_timeout: float = Field(2.0)

    # BLE bridge
    ble_device_name: str = Field("SentinelX-Node")
    ble_scan_timeout: float = Field(10.0)         # seconds to wait for each scan cycle
    ble_service_uuid: str = Field("12345678-1234-1234-1234-123456789abc")
    ble_char_uuid: str = Field("12345678-1234-1234-1234-123456789ab0")

    # Shared
    post_timeout: float = Field(8.0)              # HTTP request timeout (seconds)
    log_level: str = Field("INFO")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
