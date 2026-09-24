import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Company


DatabaseSession = Annotated[Session, Depends(get_db)]


def get_current_company(
    session: DatabaseSession,
    x_company_id: Annotated[str | None, Header()] = None,
) -> Company:
    settings = get_settings()
    if not settings.demo_mode:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Authentication provider is not configured.",
        )
    company = session.scalar(select(Company).where(Company.slug == settings.demo_company_slug))
    if company is None:
        raise HTTPException(status_code=503, detail="Demo company has not been initialized.")
    if x_company_id:
        try:
            requested_id = uuid.UUID(x_company_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid X-Company-ID header.") from exc
        if requested_id != company.id:
            raise HTTPException(status_code=403, detail="The demo identity is not a member of that company.")
    return company


CurrentCompany = Annotated[Company, Depends(get_current_company)]

