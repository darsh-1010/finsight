import enum
import uuid
from sqlalchemy import Column, Integer, String, ForeignKey, Enum, DateTime, Text, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class ScrapingFrequency(str, enum.Enum):
    HOURLY = "HOURLY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class IngestedPDF(Base):
    __tablename__ = "ingested_pdfs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationship
    user = relationship("User", back_populates="ingested_pdfs")


class ScrapingURL(Base):
    __tablename__ = "scrapping_url"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    frequency_for_scrapping = Column(
        Enum(ScrapingFrequency),
        nullable=False,
        default=ScrapingFrequency.WEEKLY
    )
    content_deletion = Column(
        Enum(ScrapingFrequency),
        nullable=False,
        default=ScrapingFrequency.MONTHLY
    )
    # Relationship
    sub_urls = relationship("ScrapingSubURL", back_populates="scraping_url", cascade="all, delete-orphan")


class ScrapingSubURL(Base):
    __tablename__ = "scraping_sub_url"

    id = Column(Integer, primary_key=True, index=True)
    scraping_url_id = Column(Integer, ForeignKey("scrapping_url.id"), nullable=False)
    source = Column(String, nullable=False)
    url = Column(String, nullable=False)
    title = Column(String, nullable=False)
    summary = Column(String, nullable=True)
    published_date = Column(DateTime, nullable=True)
    scraped_at = Column(DateTime, nullable=True)
    scraper_version = Column(String, nullable=True)
    document_id = Column(UUID(as_uuid=True),unique=True, nullable=False)

    # Relationship
    scraping_url = relationship("ScrapingURL", back_populates="sub_urls")


class ScrapingStatus(str, enum.Enum):
    QUEUED = "queued"
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ScrapingJobHistory(Base):
    __tablename__ = "scraping_job_history"

    id = Column(Integer, primary_key=True, index=True)

    run_id = Column(String, nullable=False, index=True)

    job_id = Column(String, unique=True, nullable=False, index=True)

    website_id = Column(
        Integer,
        ForeignKey("scrapping_url.id"),
        nullable=False
    )

    name = Column(String, nullable=False)

    status = Column(
        Enum(ScrapingStatus),
        nullable=False
    )

    queued_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    in_progress_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    error = Column(Text, nullable=True)

    scraping_url = relationship("ScrapingURL")
    