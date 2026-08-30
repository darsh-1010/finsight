"""Shared resilience helpers for scraper reliability.

This module centralises retry classification, backoff policy, bot-block
detection, and Playwright readiness waits so all scrapers follow the same
runtime rules.

Key capabilities:
- ``classify_failure()``     — maps raw exceptions to actionable categories
- ``build_retry_decision()`` — produces structured retry/delay decisions
- ``detect_bot_block()``     — checks rendered HTML for WAF challenge signals
- ``probe_available_selectors()`` — discovers which selectors exist in the DOM
- ``wait_for_any_selector()`` — waits for the first matching CSS selector
- ``wait_for_post_action_settle()`` — settles page after a click/navigation
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from playwright.async_api import Error as PlaywrightError

logger = logging.getLogger(__name__)

# Standard exceptions to ignore/retry in scraper flows (excluding Cancelling and SystemExit)
SCRAPER_TRY_EXCEPTIONS = (
    ValueError,
    TypeError,
    AttributeError,
    RuntimeError,
    asyncio.TimeoutError,
    PlaywrightError,
)

# ──────────────────────────────────────────────
# WAF / Bot-block signal vocabulary
# These strings appear in the page when a WAF intercepts the request.
# ──────────────────────────────────────────────
_BOT_BLOCK_SIGNALS: tuple[str, ...] = (
    "access denied",
    "please enable js",
    "enable javascript",
    "unable to authorize your request",
    "403 forbidden",
    "just a moment",  # Cloudflare Turnstile / 5-second challenge
    "ray id",  # Cloudflare block page signature
    "checking your browser",  # Cloudflare check
    "challenge-platform",  # Cloudflare challenge URL fragment
    "bot detection",
    "automated access",
    "captcha",
)

# ──────────────────────────────────────────────
# Browser launch args shared by all Chromium scrapers
# ──────────────────────────────────────────────
_CHROMIUM_STABLE_ARGS: tuple[str, ...] = (
    "--no-sandbox",
    "--disable-setuid-sandbox",
    # Use /tmp for IPC instead of /dev/shm (important inside Docker)
    "--disable-dev-shm-usage",
    "--disable-gpu",
)


class FailureCategory(StrEnum):
    """High-level failure types used for retry policy decisions."""

    TRANSIENT_NETWORK = "TRANSIENT_NETWORK"
    ANTI_BOT_BLOCK = "ANTI_BOT_BLOCK"
    SELECTOR_DRIFT = "SELECTOR_DRIFT"
    INFRA_TIMEOUT = "INFRA_TIMEOUT"
    DATA_QUALITY = "DATA_QUALITY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RetryDecision:
    """Outcome of retry-policy evaluation for one failed attempt."""

    category: FailureCategory
    should_retry: bool
    delay_seconds: float
    reason: str


def build_playwright_retry_defaults(config: dict[str, object]) -> dict[str, int]:
    """Build standardised Crawlee retry/session settings from scraper config.

    Args:
        config: Scraper config dictionary loaded from scraper_config.yaml.

    Returns:
        Keyword arguments for PlaywrightCrawler.
    """
    max_request_retries = int(config.get("max_request_retries", 3))
    max_session_rotations = int(config.get("max_session_rotations", 5))
    return {
        "max_request_retries": max(1, max_request_retries),
        "max_session_rotations": max(1, max_session_rotations),
    }


def build_chromium_launch_args() -> list[str]:
    """Return the stable Chromium launch argument list for Docker environments.

    Includes ``--disable-dev-shm-usage`` so Chromium uses /tmp for IPC
    instead of the Docker-default 64 MB /dev/shm, preventing renderer crashes.

    Returns:
        List of CLI arguments suitable for browser_launch_options["args"].
    """
    return list(_CHROMIUM_STABLE_ARGS)


def classify_failure(exc: BaseException) -> FailureCategory:
    """Classify a scraper exception into an actionable reliability category.

    Order of checks matters — ``connection closed`` MUST be checked before
    ``selector`` to avoid misclassifying a browser crash (TRANSIENT_NETWORK)
    as a layout change (SELECTOR_DRIFT) when the error message contains both
    words (e.g. ``Page.query_selector: Connection closed while reading``).

    Args:
        exc: The exception to classify.

    Returns:
        The most appropriate FailureCategory for retry policy selection.
    """
    message = str(exc).lower()
    category = FailureCategory.UNKNOWN

    if isinstance(exc, asyncio.TimeoutError):
        category = FailureCategory.INFRA_TIMEOUT
    # Connection-closed always indicates a browser/network crash — not a DOM change.
    # Must be checked before the "selector" keyword check below.
    elif any(
        token in message for token in ("connection closed", "connection reset", "econn")
    ):
        category = FailureCategory.TRANSIENT_NETWORK
    elif any(
        token in message
        for token in ("403", "access denied", "cloudflare", "captcha", "bot")
    ):
        category = FailureCategory.ANTI_BOT_BLOCK
    elif any(
        token in message
        for token in ("selector", "not found", "did not render", "no rows extracted")
    ):
        category = FailureCategory.SELECTOR_DRIFT
    elif any(
        token in message
        for token in ("dns", "tempor", "reset", "unavailable", "connection")
    ):
        category = FailureCategory.TRANSIENT_NETWORK
    elif any(token in message for token in ("empty", "low word count", "no articles")):
        category = FailureCategory.DATA_QUALITY

    return category


def build_retry_decision(
    exc: BaseException, attempt: int, max_attempts: int, source: str = "unknown"
) -> RetryDecision:
    """Return a structured retry decision for a failed scraper attempt.

    Args:
        exc: The exception that caused the failure.
        attempt: Current attempt number (1-indexed).
        max_attempts: Maximum allowed attempts.
        source: Name of the scraper for log context.

    Returns:
        A RetryDecision with should_retry, delay, and category details.
    """
    category = classify_failure(exc)

    explanations = {
        FailureCategory.ANTI_BOT_BLOCK: (
            f"The {source} website is currently blocking our connection. "
            "Taking a 10-second break to appear less like a bot."
        ),
        FailureCategory.SELECTOR_DRIFT: (
            f"The layout of the {source} page seems to have changed or content is missing. "
            "Re-checking the page structure."
        ),
        FailureCategory.TRANSIENT_NETWORK: (
            f"Temporary glitch or browser crash while accessing {source}. "
            "Retrying with exponential backoff."
        ),
        FailureCategory.INFRA_TIMEOUT: (
            f"The {source} page is responding too slowly. "
            "Retrying with a backoff strategy."
        ),
        FailureCategory.DATA_QUALITY: (
            f"The {source} page loaded but contained no useful information. "
            "Retrying to check for a partial load."
        ),
        FailureCategory.UNKNOWN: (
            f"Unexpected issue while scraping {source}. Attempting standard recovery."
        ),
    }

    if attempt >= max_attempts:
        decision = RetryDecision(
            category=category,
            should_retry=False,
            delay_seconds=0.0,
            reason="attempt_limit_reached",
        )
    elif category == FailureCategory.ANTI_BOT_BLOCK:
        decision = RetryDecision(
            category=category,
            should_retry=True,
            delay_seconds=10.0,
            reason="anti_bot_cooldown",
        )
    elif category == FailureCategory.SELECTOR_DRIFT:
        decision = RetryDecision(
            category=category,
            should_retry=True,
            delay_seconds=2.0,
            reason="selector_recheck",
        )
    elif category in (FailureCategory.TRANSIENT_NETWORK, FailureCategory.INFRA_TIMEOUT):
        decision = RetryDecision(
            category=category,
            should_retry=True,
            delay_seconds=min(16.0, 2**attempt),
            reason="exponential_backoff",
        )
    else:
        decision = RetryDecision(
            category=category,
            should_retry=False,
            delay_seconds=0.0,
            reason="non_retryable",
        )

    if decision.should_retry:
        logger.warning(
            "[SCRAPER_RETRY] Source: %s | Attempt: %s/%s | Category: %s | "
            "Reason: %s | Technical: %s | Simple: %s",
            source,
            attempt,
            max_attempts,
            category.value,
            decision.reason,
            str(exc)[:50],
            explanations[category],
        )
    elif attempt > 0:
        logger.error(
            "[SCRAPER_FATAL] Source: %s | Attempt: %s/%s | Category: %s | "
            "Technical: %s | Simple: We were unable to scrape the source after multiple attempts.",
            source,
            attempt,
            max_attempts,
            category.value,
            str(exc)[:50],
        )

    return decision


def detect_bot_block(page_html: str) -> bool:
    """Check rendered page HTML for known WAF / anti-bot challenge signals.

    Inspects the page content (lowercased) against a vocabulary of strings
    that appear when Cloudflare, Akamai, DataDome, or similar WAFs intercept
    the request.  Called after page.content() to short-circuit scraping when
    the bot is detected before any selectors are checked.

    Args:
        page_html: The full HTML string from ``await page.content()``.

    Returns:
        True if a bot-block signal is found; False otherwise.
    """
    lowered = page_html.lower()
    return any(signal in lowered for signal in _BOT_BLOCK_SIGNALS)


async def probe_available_selectors(
    page: Any,
    candidates: Sequence[str],
) -> list[str]:
    """Discover which CSS selectors currently exist in the page DOM.

    Used when all primary selectors time out (selector drift scenario).
    Logs which candidates matched so developers can update the selector list
    without a fresh manual inspection of the target site.

    Args:
        page: Playwright page object.
        candidates: CSS selector strings to probe.

    Returns:
        List of selectors that found at least one matching element.
    """
    found: list[str] = []
    for selector in candidates:
        try:
            element = await page.query_selector(selector)
            if element:
                found.append(selector)
        except SCRAPER_TRY_EXCEPTIONS:
            continue
    logger.info("[SELECTOR_PROBE] Available selectors: %s", found or "none")
    return found


async def wait_for_any_selector(
    page: Any,
    selectors: Sequence[str],
    *,
    timeout_ms: int = 20000,
    require_visible: bool = False,
    source: str = "unknown",
) -> bool:
    """Wait until at least one CSS selector appears in the DOM.

    Tries each selector in sequence within the shared timeout budget.
    Returns True on the first match.  When all selectors time out, logs
    a SELECTOR_TIMEOUT warning and returns False (does NOT raise) so that
    callers can decide whether to retry or continue.

    Args:
        page: Playwright page object.
        selectors: Candidate selectors indicating page readiness.
        timeout_ms: Maximum wait budget applied to each individual selector.
        require_visible: If True, waits for visible state; else attached.
        source: Scraper name for log context.

    Returns:
        True if any selector becomes ready within the budget; False otherwise.
    """
    state = "visible" if require_visible else "attached"

    logger.debug(
        "[WAIT_START] Source: %s | Selectors: %s | Timeout: %sms",
        source,
        selectors,
        timeout_ms,
    )

    start_time = asyncio.get_event_loop().time()
    budget_sec = timeout_ms / 1000.0

    try:
        elapsed = asyncio.get_event_loop().time() - start_time
        remaining_ms = int((budget_sec - elapsed) * 1000)
        if remaining_ms > 0:
            await page.wait_for_load_state("domcontentloaded", timeout=remaining_ms)
    except SCRAPER_TRY_EXCEPTIONS:
        pass

    for selector in selectors:
        elapsed = asyncio.get_event_loop().time() - start_time
        remaining_ms = int((budget_sec - elapsed) * 1000)
        if remaining_ms <= 0:
            break
        try:
            await page.wait_for_selector(selector, state=state, timeout=remaining_ms)
            logger.info("[SELECTOR_FOUND] Source: %s | Selector: %s", source, selector)
            return True
        except SCRAPER_TRY_EXCEPTIONS:
            continue

    logger.warning(
        "[SELECTOR_TIMEOUT] Source: %s | Selectors: %s | Timeout: %sms | "
        "Simple: No matching element found — possible selector drift or bot block.",
        source,
        selectors,
        timeout_ms,
    )
    return False


async def wait_for_post_action_settle(
    page: Any,
    selectors: Sequence[str],
    *,
    timeout_ms: int = 8000,
    source: str = "unknown",
) -> None:
    """Wait for the page to settle after a click or navigation-like action.

    Args:
        page: Playwright page object.
        selectors: Candidate selectors to wait for (can be empty).
        timeout_ms: Maximum wait budget.
        source: Scraper name for log context.
    """
    if selectors:
        await wait_for_any_selector(
            page, selectors, timeout_ms=timeout_ms, source=source
        )
        return
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    except SCRAPER_TRY_EXCEPTIONS:
        return
