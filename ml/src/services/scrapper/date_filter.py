"""Date-based article filtering utility.

Used by all scrapers to skip articles that fall outside the configured
lookback window, reducing unnecessary network requests and output size.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Common date patterns found across the 4 target websites
_DATE_PATTERNS = [
    # ISO 8601: 2026-02-23T14:30:00Z / 2026-02-23T14:30:00+00:00
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
    # Standard: 2026-02-23
    r"\d{4}-\d{2}-\d{2}",
    # US format: Feb 23, 2026 / February 23, 2026
    r"[A-Z][a-z]+ \d{1,2},? \d{4}",
    # Compact: 23 Feb 2026
    r"\d{1,2} [A-Z][a-z]+ \d{4}",
    # Slash: 02/23/2026
    r"\d{2}/\d{2}/\d{4}",
]

_MONTH_NAMES = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def _parse_regex_dates(date_str: str) -> Optional[datetime]:
    """Parse dates using regex patterns (Month DD YYYY, DD Month YYYY, MM/DD/YYYY)."""
    # Try "Month DD, YYYY" / "Month DD YYYY"
    m = re.match(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", date_str)
    if m:
        month = _MONTH_NAMES.get(m.group(1).lower())
        if month:
            try:
                return datetime(
                    int(m.group(3)),
                    month,
                    int(m.group(2)),
                    tzinfo=timezone.utc,
                )
            except ValueError:
                pass

    # Try "DD Month YYYY"
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", date_str)
    if m:
        month = _MONTH_NAMES.get(m.group(2).lower())
        if month:
            try:
                return datetime(
                    int(m.group(3)),
                    month,
                    int(m.group(1)),
                    tzinfo=timezone.utc,
                )
            except ValueError:
                pass

    # Try MM/DD/YYYY
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", date_str)
    if m:
        try:
            return datetime(
                int(m.group(3)),
                int(m.group(1)),
                int(m.group(2)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            pass

    return None


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Best-effort parsing of a date string into a timezone-aware datetime.

    Tries ISO 8601 first, then falls back to common patterns.
    Returns ``None`` if the string is empty or unparseable.
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # Strip common prefixes like "Last Updated:" or "Published:"
    date_str = re.sub(
        r"^(Last Updated|Published|Updated|Posted)\s*:\s*",
        "",
        date_str,
        flags=re.IGNORECASE,
    ).strip()

    # Strip timezone abbreviations (IST, EST, PST, etc.)
    date_str = re.sub(r"\s+[A-Z]{2,4}$", "", date_str).strip()

    # Try ISO 8601 variants
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(date_str[: len(datetime.now().strftime(fmt))], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, OverflowError):
            continue

    # Try "Mon DD, YYYY, HH:MM:SS AM/PM" (Economic Times format)
    for fmt in (
        "%b %d, %Y, %I:%M:%S %p",
        "%b %d, %Y, %I:%M %p",
        "%B %d, %Y, %I:%M:%S %p",
    ):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except (ValueError, OverflowError):
            continue

    res = _parse_regex_dates(date_str)
    if res:
        return res

    logger.debug("Could not parse date: %r", date_str)
    return None


def is_within_lookback(
    published_date: Optional[str],
    lookback_days: int,
) -> bool:
    """Return ``True`` if the article was published within the last *lookback_days*.

    If *lookback_days* is ``0`` or negative, **all** articles pass (no filter).
    If *published_date* is ``None`` or cannot be parsed, returns ``True``
    (conservative — don't skip articles we can't date).

    Args:
        published_date: ISO-format date string or any parseable date string.
        lookback_days: Number of days to look back from now.

    Returns:
        bool: True if article is within the lookback window or date is unknown.
    """
    if lookback_days <= 0:
        return True

    dt = parse_date(published_date)
    if dt is None:
        return True  # Can't parse → keep it (conservative)

    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    return dt >= cutoff
