from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api.routes import analytics, bills_of_lading, context, data_quality, documents, health, imports, invoices, shipments
from app.config import get_settings
from app.database import SessionLocal, engine
from app.models import Base, Company


settings = get_settings()


def initialize_demo_database() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        company = session.scalar(select(Company).where(Company.slug == settings.demo_company_slug))
        if company is None:
            session.add(
                Company(
                    name="Demo Logistics SIA",
                    slug=settings.demo_company_slug,
                    default_currency="EUR",
                    registration_number=settings.demo_company_registration_number,
                    vat_number=settings.demo_company_vat_number,
                )
            )
            session.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.demo_mode:
        initialize_demo_database()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.4.0",
    description="Canonical logistics data with auditable ingestion and deterministic analytics.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(context.router, prefix="/api/v1")
app.include_router(data_quality.router, prefix="/api/v1")
app.include_router(imports.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(invoices.router, prefix="/api/v1")
app.include_router(bills_of_lading.router, prefix="/api/v1")
app.include_router(shipments.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
