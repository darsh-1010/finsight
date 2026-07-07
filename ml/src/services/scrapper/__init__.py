"""Scrapper service exports."""

from .base import BaseScraper, ScraperResult
from .bofa_private_bank_scraper import BofAPrivateBankScraper
from .economic_times_scraper import EconomicTimesScraper
from .jefferies_scraper import JefferiesScraper
from .man_institute_scraper import ManInstituteScraper
from .morganstanly import MorganStanleyScraper
from .pdf_scraper import PDFScraper
from .schwab import SchwabScraper
from .scrapper_service import ScrapperService
from .seeking_alpha_scraper import SeekingAlphaScraper

__all__ = [
    "BaseScraper",
    "ScraperResult",
    "PDFScraper",
    "ScrapperService",
    "SchwabScraper",
    "JefferiesScraper",
    "ManInstituteScraper",
    "MorganStanleyScraper",
    "SeekingAlphaScraper",
    "EconomicTimesScraper",
    "BofAPrivateBankScraper",
]
