"""Regression tests for the Wealth Deutsche Bank scraper."""

import asyncio

from src.services.scrapper.wealth_deutsche_bank import WealthDesktopBankScraper


def test_shared_pdf_is_only_used_once(monkeypatch):
    """Shared PDFs should not be reused as article content across multiple pages."""
    scraper = WealthDesktopBankScraper(lookback_days=15, max_articles=10, output_file="outputs/test.json")
    scraper.used_pdf_urls.add("https://example.com/shared.pdf")

    async def fail_if_called(_url):
        raise AssertionError("PDF scraper should not be called for an already-used PDF")

    monkeypatch.setattr(
        "src.services.scrapper.wealth_deutsche_bank._pdf_scraper.scrape",
        fail_if_called,
    )

    content = asyncio.run(scraper._extract_content(
        type("Ctx", (), {"request": type("Req", (), {"url": "https://example.com/article"})()})(),
        {
            "pdfLinks": [{"href": "https://example.com/shared.pdf", "text": "PDF"}],
            "body": "HTML fallback body",
        },
    ))

    assert content == "HTML fallback body"
