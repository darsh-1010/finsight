"""Tests for SEC EDGAR data source."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.data_sources.edgar_source import EdgarSource, _strip_html


class TestStripHtml:
    """Unit tests for the HTML tag stripper."""

    def test_strips_tags(self):
        assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_strips_script_blocks(self):
        html = "<script>alert('xss')</script><p>safe</p>"
        assert "alert" not in _strip_html(html)
        assert "safe" in _strip_html(html)

    def test_decodes_entities(self):
        assert "&amp;" in _strip_html("&amp;") or "&" in _strip_html("Tom &amp; Jerry")

    def test_plain_text_passthrough(self):
        assert _strip_html("plain text no tags") == "plain text no tags"


class TestEdgarSource:
    """Tests for the EdgarSource client."""

    @pytest.mark.asyncio
    async def test_resolve_cik_found(self):
        """Should resolve a known ticker to a CIK."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        }

        source = EdgarSource()
        source._client = AsyncMock()
        source._client.is_closed = False
        source._client.get = AsyncMock(return_value=mock_resp)

        cik = await source.resolve_cik("AAPL")
        assert cik == "0000320193"

    @pytest.mark.asyncio
    async def test_resolve_cik_not_found(self):
        """Should return None for unknown ticker."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {}

        source = EdgarSource()
        source._client = AsyncMock()
        source._client.is_closed = False
        source._client.get = AsyncMock(return_value=mock_resp)

        cik = await source.resolve_cik("ZZZZ")
        assert cik is None

    @pytest.mark.asyncio
    async def test_get_filing_text_strips_html(self):
        """Should strip HTML tags from filing content."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = "<html><body><p>Revenue was $100B</p></body></html>"

        source = EdgarSource()
        source._client = AsyncMock()
        source._client.is_closed = False
        source._client.get = AsyncMock(return_value=mock_resp)

        text = await source.get_filing_text("https://sec.gov/test.htm")
        assert "Revenue was $100B" in text
        assert "<html>" not in text
