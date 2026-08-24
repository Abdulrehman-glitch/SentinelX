import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.ingest_credential import INGEST_SCOPES


class IngestCredentialCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    scopes: list[str] | None = Field(
        default=None,
        description=f"Defaults to ['metrics:write']. Supported: {list(INGEST_SCOPES)}.",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="Optional hard expiry, so a key issued for a migration stops "
        "working without anyone having to remember to revoke it.",
    )


class IngestCredentialResponse(BaseModel):
    """Everything about a key EXCEPT the key.

    `token_hash` is deliberately absent. It is not the secret, but publishing it
    would let anyone holding this response confirm a guessed key offline.
    """

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    key_prefix: str
    key_last_four: str
    scopes: list[str]
    created_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    expires_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class IngestCredentialCreatedResponse(BaseModel):
    """The one and only response that carries the plaintext key.

    It is never recoverable afterwards: only a SHA-256 is stored. A client that
    loses it must rotate rather than look it up.
    """

    credential: IngestCredentialResponse
    ingest_key: str = Field(
        ...,
        description="Shown exactly once. Configure it as the OTLP exporter's "
        "Authorization header: `Authorization: Bearer <ingest_key>`.",
    )
