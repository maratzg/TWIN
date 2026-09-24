from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentCompany


router = APIRouter(tags=["context"])


class CompanyContext(BaseModel):
    id: str
    name: str
    slug: str
    default_currency: str
    authentication_mode: str


@router.get("/context", response_model=CompanyContext)
def context(company: CurrentCompany) -> CompanyContext:
    return CompanyContext(
        id=str(company.id),
        name=company.name,
        slug=company.slug,
        default_currency=company.default_currency,
        authentication_mode="documented-demo-shortcut",
    )

