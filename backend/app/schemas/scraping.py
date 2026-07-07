from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.scraping import ScrapingFrequency


class ScrapingURLUpdate(BaseModel):
    frequency_for_scrapping: ScrapingFrequency | None = None
    content_deletion: ScrapingFrequency | None = None


class ScrapingURLCreate(BaseModel):
    name: str
    url: str
    frequency_for_scrapping: ScrapingFrequency | None = ScrapingFrequency.WEEKLY
    content_deletion: ScrapingFrequency | None = ScrapingFrequency.MONTHLY


class BulkScrapingURLCreate(BaseModel):
    urls: list[ScrapingURLCreate]


class ScrapingSubURLCreate(BaseModel):
    scraping_url_id: int
    source: str
    url: str
    title: str
    summary: str | None = None
    published_date: datetime | None = None
    scraped_at: datetime | None = None
    scraper_version: str | None = None
    document_id: UUID | None = None


class DeleteDocumentsRequest(BaseModel):
    document_ids: list[UUID]


class ScrapingSubURLResponse(BaseModel):
    id: int
    scraping_url_id: int
    source: str
    url: str
    title: str
    summary: str | None = None
    published_date: datetime | None = None
    scraped_at: datetime | None = None
    scraper_version: str | None = None
    document_id: UUID | None = None

    class Config:
        from_attributes = True


class ScrapingURLResponse(BaseModel):
    id: int
    name: str
    url: str
    frequency_for_scrapping: ScrapingFrequency
    content_deletion: ScrapingFrequency
    sub_urls: list[ScrapingSubURLResponse] = []
    status: str | None = None
    job_id: str | None = None

    class Config:
        from_attributes = True


class ScrapingURLPublicResponse(BaseModel):
    id: int
    name: str
    url: str
    frequency_for_scrapping: ScrapingFrequency
    content_deletion: ScrapingFrequency

    class Config:
        from_attributes = True


class IngestedPDFMetadata(BaseModel):
    id: UUID
    name: str
    url: str

    class Config:
        from_attributes = True


class ScrapingJobHistoryResponse(BaseModel):
    id: int
    run_id: str
    job_id: str
    website_id: int
    name: str
    status: str
    queued_at: datetime | None = None
    started_at: datetime | None = None
    in_progress_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None

    class Config:
        from_attributes = True


class MLScraperRequest(BaseModel):
    doc_id: str
    s3_url: str
    store_in_vector_db: bool = True
