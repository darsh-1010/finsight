"""Shared Camoufox browser plugin for stealthed Firefox automation.

Camoufox is a hardened Firefox build that randomises TLS fingerprint,
canvas, WebGL, audio context, and system fonts per launch.  This makes
it significantly harder for WAF solutions (Akamai, Cloudflare, DataDome)
to fingerprint and block the browser compared to standard headless Chromium.

All scrapers that target sites with advanced bot detection MUST use this
module instead of instantiating PlaywrightCrawler with a plain browser_type.

Usage:
    from src.services.scrapper.camoufox_plugin import CamoufoxPlugin, build_camoufox_pool
    crawler = PlaywrightCrawler(browser_pool=build_camoufox_pool(), ...)
"""

from camoufox import AsyncNewBrowser
from crawlee.browsers import (BrowserPool, PlaywrightBrowserController,
                              PlaywrightBrowserPlugin)
from typing_extensions import override


class CamoufoxPlugin(PlaywrightBrowserPlugin):
    """Playwright browser plugin that launches a stealthed Camoufox Firefox instance.

    Overrides the default Chromium launch so Crawlee uses Firefox with full
    fingerprint randomisation.  Each new_browser() call produces a fresh
    browser with a different identity — critical for session isolation.
    """

    @override
    async def new_browser(self) -> PlaywrightBrowserController:
        """Launch a new stealthed Camoufox Firefox browser.

        Returns:
            PlaywrightBrowserController wrapping the Camoufox browser instance.

        Raises:
            RuntimeError: If the Playwright context is not initialised yet.
        """
        if not self._playwright:
            raise RuntimeError(
                "[CAMOUFOX] Playwright browser plugin is not initialised."
            )

        # Force headless mode to prevent headed browser XServer display errors in Docker
        launch_opts = self._browser_launch_options.copy()
        launch_opts["headless"] = True

        return PlaywrightBrowserController(
            browser=await AsyncNewBrowser(self._playwright, **launch_opts),
            # One page per browser: prevents cross-session fingerprint bleed
            max_open_pages_per_browser=1,
            # Camoufox generates its own realistic headers — disable Crawlee's generator
            header_generator=None,
        )


def build_camoufox_pool() -> BrowserPool:
    """Instantiate a BrowserPool backed by a single CamoufoxPlugin.

    Returns:
        BrowserPool configured to launch stealthed Firefox browsers.
    """
    return BrowserPool(plugins=[CamoufoxPlugin()])
