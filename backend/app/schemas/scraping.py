from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel
from app.models.scraping import ScrapingFrequency


class ScrapingURLUpdate(BaseModel):
    frequency_for_scrapping: Optional[ScrapingFrequency] = None
    content_deletion: Optional[ScrapingFrequency] = None

class ScrapingURLCreate(BaseModel):
    name: str
    url: str
    frequency_for_scrapping: Optional[ScrapingFrequency] = ScrapingFrequency.WEEKLY
    content_deletion: Optional[ScrapingFrequency] = ScrapingFrequency.MONTHLY

class BulkScrapingURLCreate(BaseModel):
    urls: list[ScrapingURLCreate]


class ScrapingSubURLCreate(BaseModel):
    scraping_url_id: int
    source: str
    url: str
    title: str
    summary: Optional[str] = None
    published_date: Optional[datetime] = None
    scraped_at: Optional[datetime] = None
    scraper_version: Optional[str] = None
    document_id: Optional[UUID] = None


class DeleteDocumentsRequest(BaseModel):
    document_ids: list[UUID]


class ScrapingSubURLResponse(BaseModel):
    id: int
    scraping_url_id: int
    source: str
    url: str
    title: str
    summary: Optional[str] = None
    published_date: Optional[datetime] = None
    scraped_at: Optional[datetime] = None
    scraper_version: Optional[str] = None
    document_id: Optional[UUID] = None

    class Config:
        from_attributes = True


class ScrapingURLResponse(BaseModel):
    id: int
    name: str
    url: str
    frequency_for_scrapping: ScrapingFrequency
    content_deletion: ScrapingFrequency
    sub_urls: list[ScrapingSubURLResponse] = []
    status: Optional[str] = None
    job_id: Optional[str] = None

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
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    in_progress_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    class Config:
        from_attributes = True


class MLScraperRequest(BaseModel):
    doc_id: str
    s3_url: str
    store_in_vector_db: bool = True
