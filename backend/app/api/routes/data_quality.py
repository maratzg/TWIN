from fastapi import APIRouter

from app.api.deps import CurrentCompany, DatabaseSession
from app.schemas.imports import DataQualitySummary
from app.services.review_service import ImportReviewService


router = APIRouter(tags=["data-quality"])


@router.get("/data-quality", response_model=DataQualitySummary)
def data_quality(
    session: DatabaseSession,
    company: CurrentCompany,
) -> DataQualitySummary:
    return DataQualitySummary(**ImportReviewService(session, company.id).data_quality())
