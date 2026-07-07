from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.models.chat import ChatSession, ChatMessage
from app.models.scraping import ScrapingSubURL, ScrapingURL
from app.schemas.chat import MLChatMessage as ChatMessageSchema
from app.schemas.scraping import ScrapingSubURLCreate, ScrapingSubURLResponse, DeleteDocumentsRequest

def verify_ml_token(x_ml_token: str = Header(..., description="Secret token from ML server")):
    if x_ml_token != settings.ML_SERVER_SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid token")

router = APIRouter(
    prefix="/api/v1/ml-data-transfer",
    tags=["ML Data Transfer"],
    dependencies=[Depends(verify_ml_token)]
)

@router.get("/chat-history/{session_id}", response_model=List[ChatMessageSchema])
def get_ml_chat_history(
    session_id: uuid.UUID,
    limit: Optional[int] = Query(6, description="Dynamic limit to get the last N chats"),
    db: Session = Depends(deps.get_db)
):
    session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
        
    query = db.query(ChatMessage).filter(ChatMessage.session_id == session.id)
    
    if limit:
        # Order by created_at DESC to get the latest `limit` messages, then reverse to return chronologically
        query = query.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc()).limit(limit)
        messages = query.all()
        messages.reverse()
    else:
        # If no limit, order naturally by ascending
        query = query.order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        messages = query.all()
        
    return messages

@router.post("/scraping-content", status_code=201)
def create_ml_sub_urls(
    request: list[ScrapingSubURLCreate],
    db: Session = Depends(deps.get_db)
):
    try:
        unique_url_ids = {item.scraping_url_id for item in request}
        if unique_url_ids:
            valid_urls = db.query(ScrapingURL.id).filter(ScrapingURL.id.in_(unique_url_ids)).all()
            valid_url_ids = {url.id for url in valid_urls}
            invalid_ids = unique_url_ids - valid_url_ids
            if invalid_ids:
                raise HTTPException(
                    status_code=404,
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
            "message": f"Successfully ingested {len(new_sub_urls)} scraping-content",
            "count": len(new_sub_urls),
        }

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Database operation failed",
        ) from exc


@router.delete("/scraping-content", status_code=200)
def delete_ml_sub_urls(
    request: DeleteDocumentsRequest,
    db: Session = Depends(deps.get_db)
):
    try:
        deleted_count = db.query(ScrapingSubURL).filter(ScrapingSubURL.document_id.in_(request.document_ids)).delete(synchronize_session=False)
        db.commit()
        return {"message": f"Successfully deleted {deleted_count} sub-URLs"}
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database operation failed") from exc
