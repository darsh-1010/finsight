from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.scraping import ScrapingURL
from app.schemas.scraping import ScrapingURLPublicResponse

router = APIRouter(prefix="/api/v1/scraping", tags=["Scraping"])


@router.get("/urls", response_model=list[ScrapingURLPublicResponse])
async def get_scraping_urls(
    db: Session = Depends(get_db),
):
    """
    Fetch all scraping URLs. Accessible by all authenticated users.
    """
    return db.query(ScrapingURL).all()
