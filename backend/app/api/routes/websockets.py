from __future__ import annotations

import asyncio
import json
import logging
from typing import List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import desc

from app.core.database import SESSION_LOCAL
from app.models.scraping import ScrapingJobHistory, ScrapingURL
from app.services.scraper_service import sync_active_jobs

router = APIRouter(tags=["WebSockets"])
logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(
        self,
        message: str,
        websocket: WebSocket,
    ) -> None:
        await websocket.send_text(message)

    async def broadcast(self, message: str) -> None:
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except (RuntimeError, WebSocketDisconnect, Exception) as e:
                logger.warning("WebSocket send failed: %s", e)
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection)


manager = ConnectionManager()


async def sync_and_broadcast_jobs() -> None:
    while True:
        try:
            if manager.active_connections:
                with SESSION_LOCAL() as db:
                    await sync_active_jobs(db)

                    urls = db.query(ScrapingURL).all()
                    result = []

                    for url in urls:
                        latest_job = (
                            db.query(ScrapingJobHistory)
                            .filter(ScrapingJobHistory.website_id == url.id)
                            .order_by(desc(ScrapingJobHistory.id))
                            .first()
                        )

                        result.append(
                            {
                                "id": url.id,
                                "name": url.name,
                                "url": url.url,
                                "frequency_for_scrapping": (
                                    url.frequency_for_scrapping.value
                                    if url.frequency_for_scrapping
                                    else None
                                ),
                                "content_deletion": (
                                    url.content_deletion.value
                                    if url.content_deletion
                                    else None
                                ),
                                "status": (
                                    latest_job.status.value
                                    if latest_job
                                    else None
                                ),
                                "job_id": (
                                    latest_job.job_id
                                    if latest_job
                                    else None
                                ),
                            }
                        )

                    payload = json.dumps(
                        {
                            "type": "SCRAPING_STATUS",
                            "data": result,
                        }
                    )

                    await manager.broadcast(payload)

        except (RuntimeError, ValueError) as exc:
            logger.exception("Error in background sync: %s", exc)

        await asyncio.sleep(5)


@router.on_event("startup")
async def startup_event() -> None:
    asyncio.create_task(sync_and_broadcast_jobs())


@router.websocket("/ws")
@router.websocket("/api/v1/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(
                f"You wrote: {data}",
                websocket,
            )
            await manager.broadcast(f"Client says: {data}")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast("A client disconnected")
        