from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.core.database import engine
from app.models.scraping import (
    ScrapingFrequency,
    ScrapingJobHistory,
    ScrapingSubURL,
    ScrapingURL,
)

SESSION_LOCAL = sessionmaker(bind=engine)

SCRAPING_DATA = [
    {
        "name": "schwab",
        "url": "https://www.schwab.com/learn/story",
        "frequency_for_scrapping": ScrapingFrequency.WEEKLY,
        "content_deletion": ScrapingFrequency.MONTHLY,
    },
    {
        "name": "jefferies",
        "url": "https://www.jefferies.com/insights/",
        "frequency_for_scrapping": ScrapingFrequency.WEEKLY,
        "content_deletion": ScrapingFrequency.MONTHLY,
    },
    {
        "name": "economic_times",
        "url": "https://economictimes.indiatimes.com/markets/",
        "frequency_for_scrapping": ScrapingFrequency.WEEKLY,
        "content_deletion": ScrapingFrequency.MONTHLY,
    },
    {
        "name": "goldmansachs",
        "url": "https://www.goldmansachs.com/insights/outlooks",
        "frequency_for_scrapping": ScrapingFrequency.WEEKLY,
        "content_deletion": ScrapingFrequency.MONTHLY,
    },
    {
        "name": "barrons",
        "url": "https://www.barrons.com/topics/markets",
        "frequency_for_scrapping": ScrapingFrequency.WEEKLY,
        "content_deletion": ScrapingFrequency.MONTHLY,
    },
    {
        "name": "bofa_private_bank",
        "url": "https://www.privatebank.bankofamerica.com/articles/",
        "frequency_for_scrapping": ScrapingFrequency.WEEKLY,
        "content_deletion": ScrapingFrequency.MONTHLY,
    },
    {
        "name": "investing_com",
        "url": "https://www.investing.com/news/stock-market-news",
        "frequency_for_scrapping": ScrapingFrequency.WEEKLY,
        "content_deletion": ScrapingFrequency.MONTHLY,
    },
    {
        "name": "wealth_deutsche_bank",
        "url": "https://wealth.db.com/en/insights/investing-insights",
        "frequency_for_scrapping": ScrapingFrequency.MONTHLY,
        "content_deletion": ScrapingFrequency.MONTHLY,
    },
    {
        "name": "man_institute",
        "url": "https://www.man.com/insights/",
        "frequency_for_scrapping": ScrapingFrequency.DAILY,
        "content_deletion": ScrapingFrequency.MONTHLY,
    },
    {
        "name": "seeking_alpha",
        "url": "https://seekingalpha.com/news",
        "frequency_for_scrapping": ScrapingFrequency.DAILY,
        "content_deletion": ScrapingFrequency.MONTHLY,
    },
    {
        "name": "morgan_stanley",
        "url": "https://www.morganstanley.com/insights/articles",
        "frequency_for_scrapping": ScrapingFrequency.MONTHLY,
        "content_deletion": ScrapingFrequency.MONTHLY,
    },
    {
        "name": "deutsche_bank",
        "url": "https://www.db.com/media/news",
        "frequency_for_scrapping": ScrapingFrequency.DAILY,
        "content_deletion": ScrapingFrequency.MONTHLY,
    },
]


def seed_scraping_urls():
    db = SESSION_LOCAL()
    try:
        print("Cleaning up existing Scraping Job History...")
        db.query(ScrapingJobHistory).delete()

        print("Cleaning up existing Scraping Sub URLs...")
        db.query(ScrapingSubURL).delete()

        print("Cleaning up existing Scraping URLs...")
        db.query(ScrapingURL).delete()
        db.commit()

        print("Seeding new Scraping URLs...")
        for data in SCRAPING_DATA:
            new_url = ScrapingURL(**data)
            db.add(new_url)

        db.commit()
        print("Scraping URLs seeded successfully.")

    except SQLAlchemyError as exc:
        print(f"Database error seeding scraping URLs: {exc}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_scraping_urls()
