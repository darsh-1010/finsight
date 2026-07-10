"""Regression tests for the BofA PDF selection rules."""

from src.services.scrapper.bofa_private_bank_scraper import BofAPrivateBankScraper


def test_market_outlook_pages_are_allowed_for_pdf_extraction():
    """Market outlook pages should remain eligible for PDF extraction."""
    assert BofAPrivateBankScraper._is_market_outlook_page(
        "https://www.privatebank.bankofamerica.com/articles/capital-market-outlook-april-2026.html",
        "Capital Market Outlook",
        "Capital Market Outlook",
    )


def test_general_articles_are_not_allowed_for_pdf_extraction():
    """Generic insights pages should keep HTML content and skip PDF extraction."""
    assert not BofAPrivateBankScraper._is_market_outlook_page(
        "https://www.privatebank.bankofamerica.com/articles/art-fairs-and-events.html",
        "Art at Bank of America",
        "Art at Bank of America",
    )


def test_cookie_and_privacy_pdfs_are_blocked():
    """Cookie and privacy PDFs must never be downloaded."""
    assert BofAPrivateBankScraper._is_blocked_pdf_url(
        "https://www.bankofamerica.com/content/documents/privacy/Cookie_Guide_eng.pdf"
    )


def test_pdf_text_validation_rejects_cookie_guide_content():
    """Privacy boilerplate should fail validation even if a PDF was downloaded."""
    assert not BofAPrivateBankScraper._is_valid_pdf_text(
        "Cookie Guide Online Privacy Your Privacy Choices Advertising Practices",
        "Capital Market Outlook",
    )


def test_pdf_text_validation_accepts_market_outlook_content():
    """Validated market outlook PDFs should still be accepted."""
    assert BofAPrivateBankScraper._is_valid_pdf_text(
        "This capital market outlook reviews growth, inflation, and policy expectations.",
        "Capital Market Outlook",
    )
