"""Scraper mapping utilities for Website IDs."""

import os
from typing import Optional

import httpx

from src.utils.logger import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Website ID ↔ Scraper Name Mapping
# ──────────────────────────────────────────────────────────────────────────────

# Domain name → scraper key translation.
# Required because the backend API returns website hostnames (e.g. "man.com")
# while our SCRAPER_MAP uses internal short keys (e.g. "man_institute").
DOMAIN_TO_SCRAPER_KEY: dict[str, str] = {
    # Domains (legacy/original mapping)
    "man.com": "man_institute",
    "morganstanley.com": "morgan_stanley",
    "schwab.com": "schwab",
    "jefferies.com": "jefferies",
    "seekingalpha.com": "seeking_alpha",
    "economictimes.indiatimes.com": "economic_times",
    "goldmansachs.com": "goldmansachs",
    "barrons.com": "barrons",
    "newsroom.bankofamerica.com": "bofa_private_bank",
    "investing.com/news/stock-market-news": "investing_com",
    "db.com": "deutsche_bank",
    "wealth.db.com": "wealth_deutsche_bank",
    # Names from database
    "schwab": "schwab",
    "economic_times": "economic_times",
    "goldmansachs": "goldmansachs",
    "barrons": "barrons",
    "bofa private bank": "bofa_private_bank",
    "investing.com": "investing_com",
    "wealth_deutsche_bank": "wealth_deutsche_bank",
    "man_institute": "man_institute",
    "seeking_alpha": "seeking_alpha",
    "morgan_stanley": "morgan_stanley",
    "deutsche_bank": "deutsche_bank",
    "jefferies": "jefferies",
}

# Mutable at runtime so it can be refreshed from the backend API on startup.
# Keys are the numeric website IDs from the backend database.
WEBSITE_ID_MAP: dict[int, str] = {}

# Reverse map: scraper key → website_id (built alongside WEBSITE_ID_MAP).
SCRAPER_KEY_TO_ID: dict[str, int] = {}

# Scraper key → interval in days (fetched from backend API).
WEBSITE_INTERVAL_MAP: dict[str, float] = {}


def map_frequency_to_days(frequency: str | None) -> float:
    """Map frequency string to numeric interval in days."""
    if not frequency:
        return 1.0

    freq = frequency.lower().strip()
    if freq == "monthly":
        return 30.0
    if freq == "weekly":
        return 7.0
    if freq == "daily":
        return 1.0

    return 1.0


def load_map_from_manual_config() -> None:
    """Populate WEBSITE_ID_MAP from the hardcoded mapping below."""
    manual_map: dict[int, str] = {
        1: "schwab",
        2: "jefferies",
        3: "economic_times",
        4: "goldmansachs",
        5: "barrons",
        6: "bofa_private_bank",
        7: "investing_com",
        8: "wealth_deutsche_bank",
        9: "man_institute",
        10: "seeking_alpha",
        11: "morgan_stanley",
        12: "deutsche_bank",
    }
    WEBSITE_ID_MAP.update(manual_map)
    SCRAPER_KEY_TO_ID.update({v: k for k, v in manual_map.items()})
    logger.info("[WEBSITE_MAP] Loaded %d entries from manual config.", len(manual_map))


def load_map_from_backend_api() -> None:
    """Fetch the website ID→name mapping from the backend /api/v1/scraping/urls."""
    backend_url = os.getenv("BACKEND_API_URL", "").rstrip("/")
    if not backend_url:
        logger.warning(
            "[WEBSITE_MAP] BACKEND_API_URL not set. Falling back to manual config."
        )
        load_map_from_manual_config()
        return

    endpoint = f"{backend_url}/api/v1/scraping/urls"
    api_key = os.getenv("BACKEND_API_KEY", "")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    try:
        with httpx.Client(timeout=10, headers=headers) as client:
            response = client.get(endpoint)
            response.raise_for_status()
            entries: list[dict] = response.json()

        loaded = 0
        for entry in entries:
            website_id_raw = entry.get("id")
            try:
                website_id = int(website_id_raw) if website_id_raw is not None else 0
            except (TypeError, ValueError):
                website_id = 0
            domain_name: str = entry.get("name", "")
            frequency: str = entry.get("frequency_for_scrapping", "daily")
            scraper_key = DOMAIN_TO_SCRAPER_KEY.get(domain_name)

            if website_id and scraper_key:
                WEBSITE_ID_MAP[website_id] = scraper_key
                SCRAPER_KEY_TO_ID[scraper_key] = website_id
                WEBSITE_INTERVAL_MAP[scraper_key] = map_frequency_to_days(frequency)
                loaded += 1

        if loaded == 0:
            logger.warning(
                "[WEBSITE_MAP] Backend API returned 0 entries. Falling back to manual."
            )
            load_map_from_manual_config()
            return

        logger.info(
            "[WEBSITE_MAP] Loaded %d/%d entries from backend API.", loaded, len(entries)
        )

    except (httpx.HTTPError, ValueError) as exc:
        logger.error(
            "[WEBSITE_MAP] Failed to fetch from backend API: %s. Falling back.", exc
        )
        load_map_from_manual_config()


def load_website_id_map() -> None:
    """Initialise the website ID↔scraper name maps."""
    load_map_from_backend_api()
