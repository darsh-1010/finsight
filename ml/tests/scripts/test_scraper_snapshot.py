"""Tests for the latest scheduler snapshot publisher."""

import os
from unittest.mock import MagicMock, patch

from src.scripts.scraper_snapshot import (StoredArticleRecord,
                                          publish_scheduler_snapshot)


def test_publish_scheduler_snapshot_sends_api_request() -> None:
    """Latest snapshot should send a POST request with sequential IDs in payload."""
    stored_articles = [
        StoredArticleRecord(
            source="man_institute",
            url="https://example.com/article-1",
            title="Article One",
            summary="Summary one",
            published_date="2026-04-10T07:20:57.591Z",
            scraped_at="2026-04-10T08:20:57.591Z",
            scraper_version="crawlee-1.0",
        ),
        StoredArticleRecord(
            source="jefferies",
            url="https://example.com/article-2",
            title="Article Two",
            summary="Summary two",
            published_date="2026-04-11T07:20:57.591Z",
            scraped_at="2026-04-11T08:20:57.591Z",
            scraper_version="crawlee-1.0",
        ),
    ]

    with patch.dict(os.environ, {"ML_DATA_TRANSFER_TOKEN": "test-token", "ML_DATA_TRANSFER_BASE_URL": "http://localhost:8001"}), \
         patch("src.scripts.scraper_snapshot.requests.post") as mock_post:

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        res = publish_scheduler_snapshot("20260413_120000", stored_articles)

        assert res == "API_SUCCESS"
        mock_post.assert_called_once()
        _, called_kwargs = mock_post.call_args
        assert called_kwargs["headers"]["x-ml-token"] == "test-token"
        payload = called_kwargs["json"]
        assert len(payload) == 2
        assert payload[0]["source"] == "man_institute"
        assert payload[0]["url"] == "https://example.com/article-1"
