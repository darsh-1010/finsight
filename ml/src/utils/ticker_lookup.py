"""Static ticker lookup utility.

Resolves company names to ticker symbols using yahoo_finance_tickers.json (1110 entries)
BEFORE touching the LLM or yFinance, eliminating 1-3s of latency for known companies.

Resolution strategy (3 levels, fastest-first):
  Level 1 - Exact match on original lowercase key:
             'apple' -> 'AAPL', 'hdfc bank' -> 'HDFCBANK.NS', 'tcs' -> 'TCS.NS'

  Level 2 - Exact match on suffix-normalized key:
             'Infosys Ltd' -> normalize -> 'infosys' -> 'INFY.NS'
             'Apple Inc'   -> normalize -> 'apple'   -> 'AAPL'
             ONLY added for keys that normalize to a single unique ticker.
             'Tata Motors' -> 'tata' and 'Tata Power' -> 'tata' both hit the same norm
             -> 2 tickers -> EXCLUDED. Bare 'Tata' falls through to LLM.

  Level 3 - Unambiguous first-word prefix (single-word queries, built from original keys):
             'Reliance' -> prefix 'reliance' -> 1 unique ticker -> 'RELIANCE.NS'
             'HDFC'     -> prefix 'hdfc'     -> 2 tickers (Bank + Life) -> None (LLM path)
             'Tata'     -> prefix 'tata'     -> 9 tickers -> None (LLM path)

  If all 3 levels fail -> return None -> TickerService LLM path handles it.

Design invariants:
  - NEVER resolve ambiguous names. Return None so LLM can use conversation context.
  - Lookup tables are built ONCE at module import (O(1) per query at runtime).
  - Prefix ambiguity is tracked from ORIGINAL keys only - normalization is only applied
    to user input (it strips disambiguators that matter for ambiguity detection).
"""

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Path to the bundled ticker data file
_TICKER_FILE = Path(__file__).parents[2] / "yahoo_finance_tickers.json"

# Legal suffixes that carry no disambiguation value and can be stripped
_SUFFIX_PATTERN = re.compile(
    r"\b("
    r"ltd|limited|inc|incorporated|corp|corporation|co\.|company"
    r"|plc|se|ag|sa|nv|bv|llc|llp|lp"
    r"|group|holding|holdings"
    r"|enterprises|enterprise"
    r"|solutions|technologies|technology|tech"
    r"|financial|finance|capital"
    r"|insurance|assurance"
    r"|auto|automobile|automobiles|motors|motor"
    r"|energy|power|utilities"
    r"|networks|network|communications|telecom"
    r"|pharmaceuticals|pharmaceutical|pharma"
    r"|chemicals|chemical"
    r"|services|service"
    r"|industries|industry|industrial"
    r"|systems|system"
    r")\b",
    re.IGNORECASE,
)


def _normalize(name: str) -> str:
    """Strip legal suffixes and collapse whitespace. Returns lowercase."""
    name = name.lower().strip()
    name = _SUFFIX_PATTERN.sub("", name)
    return re.sub(r"\s+", " ", name).strip()


def _build_tables(raw_data: dict) -> tuple[dict, dict]:
    """Build exact_lookup and prefix_lookup from raw JSON data.

    Level 1 (original keys) and Level 3 (prefix table) use only the ORIGINAL
    JSON keys. This is critical: normalization strips disambiguators like 'motors'
    and 'steel', so we cannot use normalized keys to test for ambiguity.

    Level 2 (normalized keys) is added only when the normalized form is unambiguous
    (maps to exactly 1 unique ticker across all JSON entries).
    """
    # Level 1: original keys (always unambiguous within the JSON)
    exact_lookup: dict[str, str] = {}
    for raw_key, ticker in raw_data.items():
        exact_lookup[raw_key.lower()] = ticker

    # Level 2: normalized keys - only if unambiguous
    # First pass: collect all tickers that map to each normalized form
    norm_to_tickers: dict[str, set] = defaultdict(set)
    for raw_key, ticker in raw_data.items():
        norm = _normalize(raw_key)
        # Only relevant if normalization actually changed the key
        if norm and norm != raw_key.lower():
            norm_to_tickers[norm].add(ticker)

    # Second pass: write only unambiguous normalized forms
    for norm, tickers in norm_to_tickers.items():
        if len(tickers) == 1 and norm not in exact_lookup:
            exact_lookup[norm] = list(tickers)[0]

    # Level 3: prefix table from ORIGINAL keys only
    # Example why this matters:
    #   'Tata Motors' -> first_word='tata' -> TATAMOTORS.NS
    #   'Tata Steel'  -> first_word='tata' -> TATASTEEL.NS
    #   => 2 tickers for 'tata' => AMBIGUOUS => excluded from prefix_lookup
    #   'Reliance Industries' -> first_word='reliance' -> RELIANCE.NS (only 1) => included
    original_prefix_to_tickers: dict[str, set] = defaultdict(set)
    for raw_key, ticker in raw_data.items():
        words = raw_key.lower().split()
        if words:
            original_prefix_to_tickers[words[0]].add(ticker)

    prefix_lookup: dict[str, str] = {
        prefix: list(tickers)[0]
        for prefix, tickers in original_prefix_to_tickers.items()
        if len(tickers) == 1
    }

    return exact_lookup, prefix_lookup


def _load() -> tuple[dict, dict]:
    """Load ticker file and build lookup tables. Called once at module import."""
    try:
        with open(_TICKER_FILE, encoding="utf-8") as f:
            raw_data = json.load(f)
        exact, prefix = _build_tables(raw_data)
        logger.info(
            "[TICKER_LOOKUP] Loaded %d entries -> %d exact keys, %d unambiguous prefix keys",
            len(raw_data),
            len(exact),
            len(prefix),
        )
        return exact, prefix
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(
            "[TICKER_LOOKUP] Failed to load %s: %s - static lookup disabled",
            _TICKER_FILE,
            e,
        )
        return {}, {}


# Module-level lookup tables (built once at import, O(1) per query)
_EXACT_LOOKUP, _PREFIX_LOOKUP = _load()


def resolve(name: str) -> str | None:
    """Resolve a company name to a ticker using the static JSON lookup.

    Returns the ticker string if resolved unambiguously, or None if:
      - The company is not in the JSON -> LLM path handles it
      - Multiple tickers match (ambiguous) -> LLM uses conversation context

    This function NEVER raises. It is safe to call before any LLM or network call.

    Args:
        name: Company name as extracted from user query (any casing, with/without suffixes)

    Returns:
        Ticker string e.g. 'HDFCBANK.NS', 'AAPL' or None
    """
    if not name or not name.strip():
        return None

    # Level 1: Exact match on original lowercase key
    raw = name.lower().strip()
    if ticker := _EXACT_LOOKUP.get(raw):
        logger.debug("[TICKER_LOOKUP] L1 exact: '%s' -> %s", name, ticker)
        return ticker

    # Level 2: Exact match on suffix-normalized form (e.g. 'Infosys Ltd' -> 'infosys')
    norm = _normalize(name)
    if norm and (ticker := _EXACT_LOOKUP.get(norm)):
        logger.debug(
            "[TICKER_LOOKUP] L2 normalized: '%s' (norm='%s') -> %s", name, norm, ticker
        )
        return ticker

    # Level 3: Unambiguous single-word prefix
    # Use only the FIRST word of the normalized query as the prefix.
    # 'Reliance Industries Limited' -> norm='reliance' -> L3 prefix hit
    # 'HDFC'  -> norm='hdfc'  -> prefix_lookup has no 'hdfc' (2 HDFC stocks) -> None
    # 'Tata'  -> norm='tata'  -> prefix_lookup has no 'tata' (9 Tata stocks)  -> None
    first_word = norm.split()[0] if norm.split() else ""
    if first_word and (ticker := _PREFIX_LOOKUP.get(first_word)):
        logger.debug(
            "[TICKER_LOOKUP] L3 prefix: '%s' (first='%s') -> %s",
            name,
            first_word,
            ticker,
        )
        return ticker

    logger.debug("[TICKER_LOOKUP] Miss: '%s' -> LLM fallback", name)
    return None


def is_loaded() -> bool:
    """True if the ticker data file was successfully loaded."""
    return bool(_EXACT_LOOKUP)
