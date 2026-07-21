"""
Organization management — platform admin only for most actions.
"""

from fastapi import APIRouter, Depends, HTTPException, status
import uuid

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.organization import Organization
from app.models.user import User

router = APIRouter(prefix="/organizations", tags=["Organizations"])


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    plan: str
    is_active: bool

    model_config = {"from_attributes": True}


class OrganizationCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    plan: str = "professional"


@router.get("", response_model=list[OrganizationResponse])
def list_organizations(
    limit: int = 200,
    current_user: User = Depends(require_role(["platform_admin"])),
    db: Session = Depends(get_db),
) -> list[Organization]:
    safe_limit = min(max(limit, 1), 1000)
    return list(db.scalars(select(Organization).order_by(Organization.name).limit(safe_limit)))


@router.get("/me", response_model=OrganizationResponse)
def get_my_organization(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Organization:
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No organization associated with this account.",
        )
    org = db.get(Organization, current_user.organization_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    return org


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreateRequest,
    current_user: User = Depends(require_role(["platform_admin"])),
    db: Session = Depends(get_db),
) -> Organization:
    existing = db.scalar(select(Organization).where(Organization.slug == payload.slug))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Organization slug already exists.")

    org = Organization(
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        plan=payload.plan,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org
