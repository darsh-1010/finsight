import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Pattern to find a scraper section and its interval_days attribute
# Matches:
# scraper_name:
#   ...
#   interval_days: value
SCRAPER_PATTERN = (
    r"(?P<prefix>^{scraper_name}:\s*[\r\n]+"  # Scraper key + newline
    r"(?:^  .*[\r\n]+)*?)"  # Any indented lines (non-greedy)
    r"(?P<indent>  )interval_days:.*"  # The interval_days line
)


def update_scraper_intervals(
    intervals: dict[str, float], config_path: Path | None = None
) -> None:
    """Update the interval_days for scrapers in the config/scraper_config.yaml file.

    This function performs a surgical regex-based update to preserve comments
    and environment variable placeholders elsewhere in the file.

    Args:
        intervals: Map of scraper key to the new interval in days.
        config_path: Optional path to the config file (defaults to project root config).
    """
    if config_path is None:
        config_path = (
            Path(__file__).parent.parent.parent / "config" / "scraper_config.yaml"
        )

    if not config_path.exists():
        logger.error("[CONFIG_UPDATE] File not found: %s", config_path)
        return

    try:
        with open(config_path, encoding="utf-8") as file_handle:
            content = file_handle.read()

        updated_content = content
        overrides_count = 0

        for name, interval in intervals.items():
            # Build regex for this specific scraper
            # We look for the scraper name at 2-space indentation (start of line + 2 spaces)
            # as seen in the scraper_config.yaml structure.
            pattern = (
                r"(?P<prefix>^  " + re.escape(name) + r":\s*[\r\n]+"
                r"(?:^    .*[\r\n]+)*?)"  # 4-space indented properties
                r"(?P<indent>    )interval_days:.*"  # The interval line
            )

            replacement = r"\g<prefix>\g<indent>interval_days: " + str(interval)

            # Use MULTILINE to allow ^ to match starts of lines
            new_content = re.sub(
                pattern, replacement, updated_content, flags=re.MULTILINE
            )

            if new_content != updated_content:
                updated_content = new_content
                overrides_count += 1
                logger.info(
                    "[CONFIG_UPDATE] Updated %s: interval_days -> %s", name, interval
                )

        if overrides_count > 0:
            # Create a backup before writing
            backup_path = config_path.with_suffix(".yaml.bak")
            with open(backup_path, "w", encoding="utf-8") as backup_handle:
                backup_handle.write(content)

            with open(config_path, "w", encoding="utf-8") as file_handle:
                file_handle.write(updated_content)

            logger.info(
                "[CONFIG_UPDATE] Successfully updated %s scrapers in %s",
                overrides_count,
                config_path,
            )
        else:
            logger.info(
                "[CONFIG_UPDATE] No changes needed or no matching scrapers found in YAML."
            )

    except (OSError, re.error) as exc:
        logger.error("[CONFIG_UPDATE] Failed to update config file: %s", exc)
        # In production, we might want to raise this, but here we fail gracefully
        # to ensure the scheduler can still try to start with existing config.


if __name__ == "__main__":
    # Self-test logic
    logging.basicConfig(level=logging.INFO)
    update_scraper_intervals({"man_institute": 7.0, "jefferies": 30.0})
