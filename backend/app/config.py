from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Logistics Intelligence Platform"
    database_url: str = "sqlite:///./logistics.db"
    demo_mode: bool = True
    demo_company_slug: str = "demo-logistics"
    cors_origins: str = "http://localhost:3000"
    document_storage_root: str = "document-storage"
    document_max_upload_bytes: int = 20 * 1024 * 1024
    document_high_confidence_threshold: float = 0.85
    document_classification_threshold: float = 0.75
    document_amount_tolerance: str = "0.02"
    document_weight_tolerance: str = "1.000"
    analytics_margin_drop_pp: str = "3.0"
    analytics_cost_increase_pct: str = "10.0"
    analytics_revenue_change_pct: str = "10.0"
    analytics_volume_change_pct: str = "25.0"
    analytics_customer_concentration_pct: str = "30.0"
    analytics_route_concentration_pct: str = "35.0"
    analytics_receivable_concentration_pct: str = "30.0"
    analytics_payment_delay_days: str = "7.0"
    analytics_company_margin_decline_pp: str = "1.0"
    analytics_margin_improvement_pp: str = "3.0"
    analytics_expensive_shipment_zscore: str = "3.0"
    analytics_min_route_shipments: int = 8
    analytics_min_paid_invoices: int = 5
    analytics_min_receivable_invoices: int = 5
    analytics_min_anomaly_observations: int = 8
    demo_company_registration_number: str = "40000000000"
    demo_company_vat_number: str = "LV40000000000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def document_storage_path(self) -> Path:
        return Path(self.document_storage_root).expanduser().resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
