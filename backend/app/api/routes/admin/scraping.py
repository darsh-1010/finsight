import io
import os
import uuid
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, HttpUrl
from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.core.config import settings
from app.models.scraping import (
    IngestedPDF,
    ScrapingJobHistory,
    ScrapingSubURL,
    ScrapingURL,
)
from app.models.users import User
from app.schemas.scraping import (
    BulkScrapingURLCreate,
    IngestedPDFMetadata,
    ScrapingJobHistoryResponse,
    ScrapingSubURLCreate,
    ScrapingSubURLResponse,
    ScrapingURLResponse,
    ScrapingURLUpdate,
)
from app.services.s3_service import s3_service
from app.services.scraper_service import (
    delete_document_from_ml,
    sync_active_jobs,
    trigger_scraper_job,
)

router = APIRouter(prefix="/scraping", tags=["Admin Scraping"])


class ScrapeURLRequest(BaseModel):
    url: HttpUrl


def extract_name_from_url(url: str) -> str:
    """Extract readable filename from URL."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    name = os.path.basename(path)
    return name or parsed.netloc


async def download_pdf_from_url(url_str: str) -> bytes:
    """Download PDF content safely."""
    async with httpx.AsyncClient() as client:
        response = await client.get(url_str, follow_redirects=True)

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Failed to download PDF from URL: {url_str}. "
                f"Status code: {response.status_code}"
            ),
        )

    content_type = response.headers.get("content-type", "")
    if "application/pdf" not in content_type.lower() and not url_str.lower().endswith(
        ".pdf"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The provided URL does not appear to be a PDF file.",
        )

    return response.content


@router.post("/upload-pdf", status_code=status.HTTP_201_CREATED)
async def upload_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Upload PDF to S3 and store metadata."""

    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are allowed",
        )

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file name",
        )

    try:
        file_name = os.path.basename(file.filename)
        object_name = f"scraping_upload/{file_name}"

        await s3_service.upload_file(file, object_name=object_name)

        existing = (
            db.query(IngestedPDF)
            .filter(
                IngestedPDF.name == file_name,
                IngestedPDF.user_id == current_user.id,
            )
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Scraping record already exists for this file",
            )

        ingested_pdf = IngestedPDF(
            name=file_name,
            url=object_name,
            user_id=current_user.id,
        )

        db.add(ingested_pdf)
        db.commit()
        db.refresh(ingested_pdf)

        presigned_url = await s3_service.get_presigned_url(
            object_name, content_type="application/pdf", inline=False
        )

        # Trigger ML Scraper job
        await trigger_scraper_job(doc_id=str(ingested_pdf.id), s3_url=presigned_url)

        return {
            "message": "File uploaded successfully and scraper triggered",
            "scraping_id": ingested_pdf.id,
            "name": ingested_pdf.name,
            "presigned_url": presigned_url,
        }

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed",
        ) from exc


@router.post("/ingest-scrape-url", status_code=status.HTTP_201_CREATED)
async def scrape_url(
    request: ScrapeURLRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Download PDF from URL, upload to S3, save metadata."""

    try:
        url_str = str(request.url)
        pdf_content = await download_pdf_from_url(url_str)

        name = extract_name_from_url(url_str)
        if not name.lower().endswith(".pdf"):
            name = f"{name}.pdf"

        unique_id = str(uuid.uuid4())[:8]
        object_name = f"scraping_upload/{unique_id}_{name}"

        pdf_file = io.BytesIO(pdf_content)
        await s3_service.upload_fileobj(pdf_file, object_name)

        ingested_pdf = IngestedPDF(
            name=name,
            url=object_name,
            user_id=current_user.id,
        )

        db.add(ingested_pdf)
        db.commit()
        db.refresh(ingested_pdf)

        presigned_url = await s3_service.get_presigned_url(
            object_name, content_type="application/pdf", inline=False
        )

        # Trigger ML Scraper job
        await trigger_scraper_job(doc_id=str(ingested_pdf.id), s3_url=presigned_url)

        return {
            "message": "URL ingested, PDF uploaded to S3 and scraper triggered",
            "scraping_id": ingested_pdf.id,
            "name": ingested_pdf.name,
            "s3_path": ingested_pdf.url,
            "presigned_url": presigned_url,
        }

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Network error while downloading PDF: {exc}",
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed",
        ) from exc


@router.get("/ingested-pdf", response_model=list[IngestedPDFMetadata])
async def ingested_pdf_list(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role("admin")),
):
    """List ingested PDFs."""

    ingested_pdfs = db.query(IngestedPDF).all()

    for pdf in ingested_pdfs:
        if pdf.url and not pdf.url.startswith(("http://", "https://")):
            try:
                pdf.url = await s3_service.get_presigned_url(
                    pdf.url, content_type="application/pdf"
                )
            except HTTPException:
                continue

    return ingested_pdfs


@router.get("/urls", response_model=list[ScrapingURLResponse])
async def list_scraping_urls(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role("admin")),
):
    """List scraping URLs with latest job."""

    await sync_active_jobs(db)
    urls = db.query(ScrapingURL).all()

    for url in urls:
        latest_job = (
            db.query(ScrapingJobHistory)
            .filter(ScrapingJobHistory.website_id == url.id)
            .order_by(desc(ScrapingJobHistory.id))
            .first()
        )

        setattr(url, "status", latest_job.status if latest_job else None)
        setattr(url, "job_id", latest_job.job_id if latest_job else None)

    return urls


@router.get("/history", response_model=list[ScrapingJobHistoryResponse])
async def list_scraping_history(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role("admin")),
):
    """List scraping history."""

    return db.query(ScrapingJobHistory).order_by(desc(ScrapingJobHistory.id)).all()


@router.put("/url/{url_id}", response_model=ScrapingURLResponse)
async def update_scraping_url_settings(
    url_id: int,
    request: ScrapingURLUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role("admin")),
):
    """Update scraping URL settings."""

    scraping_url = db.query(ScrapingURL).filter(ScrapingURL.id == url_id).first()

    if not scraping_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scraping URL record not found",
        )

    if request.frequency_for_scrapping is not None:
        scraping_url.frequency_for_scrapping = request.frequency_for_scrapping

    if request.content_deletion is not None:
        scraping_url.content_deletion = request.content_deletion

    try:
        db.commit()
        db.refresh(scraping_url)
        return scraping_url

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed",
        ) from exc


@router.post("/bulk-ingest", status_code=status.HTTP_201_CREATED)
async def bulk_ingest_scraping_urls(
    request: BulkScrapingURLCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Bulk ingest scraping URLs."""

    try:
        new_urls = []

        for url_data in request.urls:
            existing = (
                db.query(ScrapingURL)
                .filter(ScrapingURL.url == str(url_data.url))
                .first()
            )

            if existing:
                continue

            new_urls.append(
                ScrapingURL(
                    name=url_data.name,
                    url=str(url_data.url),
                    frequency_for_scrapping=url_data.frequency_for_scrapping,
                    content_deletion=url_data.content_deletion,
                )
            )

        if new_urls:
            db.add_all(new_urls)
            db.commit()

        return {
            "message": f"Successfully ingested {len(new_urls)} URLs",
            "count": len(new_urls),
        }

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database bulk operation failed",
        ) from exc


@router.get("/sub-urls", response_model=list[ScrapingSubURLResponse])
async def list_scraping_sub_urls(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role("admin")),
):
    """List scraping sub URLs."""

    return db.query(ScrapingSubURL).all()


@router.post("/bulk-sub-urls", status_code=status.HTTP_201_CREATED)
async def bulk_ingest_scraping_sub_urls(
    request: list[ScrapingSubURLCreate],
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role("admin")),
):
    """Bulk ingest sub URLs."""

    try:
        unique_url_ids = {item.scraping_url_id for item in request}
        if unique_url_ids:
            valid_urls = (
                db.query(ScrapingURL.id)
                .filter(ScrapingURL.id.in_(unique_url_ids))
                .all()
            )
            valid_url_ids = {url.id for url in valid_urls}
            invalid_ids = unique_url_ids - valid_url_ids
            if invalid_ids:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Parent ScrapingURLs with ids {invalid_ids} not found",
                )

        new_sub_urls = []

        for item in request:
            existing = (
                db.query(ScrapingSubURL)
                .filter(
                    ScrapingSubURL.scraping_url_id == item.scraping_url_id,
                    ScrapingSubURL.url == str(item.url),
                )
                .first()
            )

            if existing:
                continue

            new_sub_urls.append(
                ScrapingSubURL(
                    scraping_url_id=item.scraping_url_id,
                    source=item.source,
                    url=str(item.url),
                    title=item.title,
                    summary=item.summary,
                    published_date=item.published_date,
                    scraped_at=item.scraped_at,
                    scraper_version=item.scraper_version,
                    document_id=item.document_id,
                )
            )

        if new_sub_urls:
            db.add_all(new_sub_urls)
            db.commit()

        return {
            "message": f"Successfully ingested {len(new_sub_urls)} sub-URLs",
            "count": len(new_sub_urls),
        }

    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database bulk operation for sub-URLs failed",
        ) from exc


@router.delete("/ingested-pdf/{pdf_id}", status_code=status.HTTP_200_OK)
async def delete_ingested_pdf(
    pdf_id: uuid.UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role("admin")),
):
    """Delete an ingested PDF record and its corresponding file from S3."""

    pdf = db.query(IngestedPDF).filter(IngestedPDF.id == pdf_id).first()

    if not pdf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingested PDF record not found",
        )

    try:
        # 1. Delete from ML Scraper (Vector DB)
        print(f"Triggering ML delete for document_id: {pdf.id}")
        await delete_document_from_ml(str(pdf.id))

        # 2. Delete from S3
        if pdf.url:
            print(f"Deleting file from S3: {pdf.url}")
            await s3_service.delete_file(pdf.url)

        # 3. Delete from DB
        print(f"Deleting record from DB: {pdf.id}")
        db.delete(pdf)
        db.commit()

        return {"message": "Ingested PDF and associated data deleted successfully"}

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed",
        ) from exc
    except Exception as exc:
        db.rollback()
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during deletion: {str(exc)}",
        ) from exc
