"""Scraper Registry.

This module maintains the mapping of scraper names to their implementation
classes or functions. It helps keep the main scheduler script clean and
within the line limit.
"""

from collections.abc import Callable

# ──────────────────────────────────────────────────────────────────────────────
# Scraper Service Imports
# ──────────────────────────────────────────────────────────────────────────────
# from src.services.scrapper.barrons import main as scrape_barrons
from src.services.scrapper.bofa_private_bank_scraper import BofAPrivateBankScraper
from src.services.scrapper.deutsche_bank import main as scrape_deutsche_bank
from src.services.scrapper.economic_times_scraper import EconomicTimesScraper
from src.services.scrapper.goldmansachs import main as scrape_goldmansachs
from src.services.scrapper.investing_com import main as scrape_investing
from src.services.scrapper.jefferies_scraper import JefferiesScraper
from src.services.scrapper.man_institute_scraper import ManInstituteScraper
from src.services.scrapper.morganstanly import MorganStanleyScraper
from src.services.scrapper.schwab import SchwabScraper

# from src.services.scrapper.seeking_alpha_scraper import SeekingAlphaScraper
from src.services.scrapper.wealth_deutsche_bank import (
    main as scrape_wealth_deutsche_bank,
)

# Mapping of internal names to their entry point (Class or Async function)
SCRAPER_MAP: dict[str, type | Callable] = {
    # Instance-based scrapers (Classes with scrape_async())
    "man_institute": ManInstituteScraper,
    "jefferies": JefferiesScraper,
    "morgan_stanley": MorganStanleyScraper,
    "schwab": SchwabScraper,
    # "seeking_alpha": SeekingAlphaScraper,
    "economic_times": EconomicTimesScraper,
    "bofa_private_bank": BofAPrivateBankScraper,
    # Function-based scrapers (standalone main() coroutines)
    "investing_com": scrape_investing,
    # "barrons": scrape_barrons,
    "deutsche_bank": scrape_deutsche_bank,
    "goldmansachs": scrape_goldmansachs,
    "wealth_deutsche_bank": scrape_wealth_deutsche_bank,
}
