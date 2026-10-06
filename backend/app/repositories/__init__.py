"""Tenant-scoped persistence operations."""
from app.repositories.documents import DocumentRepository
from app.repositories.invoices import InvoiceRepository

__all__ = ["DocumentRepository", "InvoiceRepository"]
