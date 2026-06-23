"""
Selenium-based screenshot capture with full-page support and DPR awareness.
"""

import os
import time

from selenium import webdriver

from .logging_config import get_logger

logger = get_logger("core.screenshot")
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager


class ScreenshotCapture:
    """
    Captures full-page screenshots using Selenium.

    DPR notes
    ---------
    When ``dpr`` > 1 Chrome is launched with ``--force-device-scale-factor``
    so the resulting PNG will be ``width * dpr`` × ``height * dpr`` pixels.
    The ImageComparator will divide by the same DPR before comparing against
    the baseline (which is always at logical / 1x resolution).
    """

    def __init__(
        self,
        browser: str = "chrome",
        headless: bool = True,
        dpr: float = 1.0,
        page_load_wait: int = 3,
    ):
        self.browser = browser.lower()
        self.headless = headless
        self.dpr = dpr
        self.page_load_wait = page_load_wait

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def capture(
        self,
        url: str,
        output_path: str,
        width: int = 1440,
        height: int = 900,
    ) -> str:
        """
        Navigate to *url*, wait for the page to settle, then save a
        full-page screenshot to *output_path*.

        Returns the resolved output_path.
        
        Logs browser type, resolution, DPR, and save location.
        """
        logger.info(f"Starting screenshot capture: browser={self.browser}, resolution={width}×{height}, dpr={self.dpr}")
        driver = self._create_driver(width, height)
        try:
            logger.debug(f"Navigating to URL: {url}")
            driver.get(url)
            time.sleep(240)
            logger.debug(f"Waiting {self.page_load_wait} seconds for page to settle")
            time.sleep(self.page_load_wait)

            # Expand window to full document height for a full-page capture
            total_height = driver.execute_script(
                "return Math.max("
                "  document.body.scrollHeight,"
                "  document.documentElement.scrollHeight,"
                "  document.body.offsetHeight,"
                "  document.documentElement.offsetHeight"
                ")"
            )
            driver.set_window_size(width, max(total_height, height))
            time.sleep(0.5)

            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            driver.save_screenshot(output_path)
            logger.info(f"Screenshot saved: {output_path}")
        finally:
            logger.debug("Closing WebDriver")
            driver.quit()

        return output_path

    # ------------------------------------------------------------------
    # Driver factories
    # ------------------------------------------------------------------

    def _create_driver(self, width: int, height: int):
        factories = {
            "chrome": self._chrome_driver,
            "firefox": self._firefox_driver,
            "edge": self._edge_driver,
        }
        factory = factories.get(self.browser)
        if factory is None:
            raise ValueError(
                f"Unsupported browser '{self.browser}'. Choose from: {list(factories)}"
            )
        return factory(width, height)

    def _chrome_driver(self, width: int, height: int):
        opts = ChromeOptions()
        if self.headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument(f"--window-size={width},{height}")
        opts.add_argument("--hide-scrollbars")
        opts.add_argument("--disable-infobars")
        opts.add_argument("--disable-extensions")
        if self.dpr != 1.0:
            opts.add_argument(f"--force-device-scale-factor={self.dpr}")

        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=opts)
        driver.set_window_size(width, height)
        return driver

    def _firefox_driver(self, width: int, height: int):
        opts = FirefoxOptions()
        if self.headless:
            opts.add_argument("--headless")

        service = FirefoxService(GeckoDriverManager().install())
        driver = webdriver.Firefox(service=service, options=opts)
        driver.set_window_size(width, height)
        return driver

    def _edge_driver(self, width: int, height: int):
        opts = EdgeOptions()
        if self.headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument(f"--window-size={width},{height}")
        if self.dpr != 1.0:
            opts.add_argument(f"--force-device-scale-factor={self.dpr}")

        service = EdgeService(EdgeChromiumDriverManager().install())
        driver = webdriver.Edge(service=service, options=opts)
        return driver
