"""
Selenium-based screenshot capture with full-page support and DPR awareness.
"""

import os
import time
from typing import Optional

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
        page_load_timeout: int = 300,
        page_data_load_wait: int = 3,
    ):
        self.browser = browser.lower()
        self.headless = headless
        self.dpr = dpr
        self.page_load_timeout = page_load_timeout
        self.page_data_load_wait = page_data_load_wait

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def capture(
        self,
        url: str,
        output_path: str,
        width: int = 1440,
        height: int = 900,
        figma_image_width: Optional[int] = None,
        figma_image_height: Optional[int] = None,
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
            driver.set_page_load_timeout(self.page_load_timeout)
            logger.debug(f"Set page load timeout to {self.page_load_timeout} seconds")
            logger.debug(f"Navigating to URL: {url}")
            driver.get(url)

            logger.debug(
                f"Waiting additional {self.page_data_load_wait} seconds for dynamic content"
            )
            time.sleep(self.page_data_load_wait)  # Ensure late dynamic content is rendered.

            # Scroll the page incrementally to trigger lazy-loading content.
            # Uses absolute scrollTo positions + explicit scroll event dispatch to
            # ensure IntersectionObserver and scroll-event listeners fire correctly.
            logger.debug("Starting page scroll to load all content")
            current_pos = 0
            scroll_step = height  # One viewport height per step

            while True:
                current_pos += scroll_step
                driver.execute_script(
                    "window.scrollTo(0, arguments[0]);"
                    "window.dispatchEvent(new Event('scroll'));"
                    "document.dispatchEvent(new Event('scroll'));",
                    current_pos,
                )
                time.sleep(1)  # Wait for lazy-loaded content to render

                page_height = driver.execute_script("return document.body.scrollHeight")
                if current_pos >= page_height:
                    logger.debug("Reached end of page")
                    break

            # Wait for any final lazy content triggered by the last scroll
            time.sleep(1.0)

            # Expand window to the maximum rendered height for full-page capture.
            # Includes document metrics and current live viewport/app height.
            post_scroll_height = driver.execute_script(
                "const body = document.body || {};"
                "const docEl = document.documentElement || {};"
                "const viewportHeight = Math.max("
                "  window.innerHeight || 0,"
                "  (window.visualViewport && window.visualViewport.height) || 0"
                ");"
                "return Math.max("
                "  body.scrollHeight || 0,"
                "  docEl.scrollHeight || 0,"
                "  body.offsetHeight || 0,"
                "  docEl.offsetHeight || 0,"
                "  body.clientHeight || 0,"
                "  docEl.clientHeight || 0,"
                "  viewportHeight"
                ");"
            )
            # Final capture size aligns to Figma width (when provided) and uses
            # max(default height, live post-scroll height, Figma height).
            default_width = int(width)
            figma_width = int(figma_image_width or 0)
            target_width = figma_width if figma_width > 0 else default_width
            default_height = int(height)
            live_height = int(post_scroll_height)
            figma_height = int(figma_image_height or 0)
            final_height = max(default_height, live_height, figma_height)
            logger.info(
                "Width selection for capture: "
                f"default_width={default_width}, "
                f"figma_image_width={figma_width}, "
                f"target_width={target_width}"
            )
            logger.info(
                "Height selection for capture: "
                f"default_height={default_height}, "
                f"post_scroll_height={live_height}, "
                f"figma_image_height={figma_height}, "
                f"final_height={final_height}"
            )
            self._set_window_size_with_viewport_alignment(
                driver=driver,
                target_width=target_width,
                target_height=final_height,
            )
            time.sleep(0.5)

            # Scroll back to the very top after resize so the header is visible
            logger.info(f"Scroll back to the very top after resize so the header is visible")
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.3)

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

    def _set_window_size_with_viewport_alignment(
        self,
        driver,
        target_width: int,
        target_height: int,
        max_attempts: int = 3,
    ) -> None:
        driver.set_window_size(target_width, target_height)
        for attempt in range(1, max_attempts + 1):
            viewport = driver.execute_script(
                "return {"
                "  width: Math.floor(window.innerWidth || 0),"
                "  height: Math.floor(window.innerHeight || 0)"
                "};"
            )
            actual_width = int(viewport.get("width", 0))
            actual_height = int(viewport.get("height", 0))
            delta_w = target_width - actual_width
            delta_h = target_height - actual_height

            logger.debug(
                "Viewport alignment attempt "
                f"{attempt}/{max_attempts}: "
                f"target={target_width}x{target_height}, "
                f"actual={actual_width}x{actual_height}, "
                f"delta={delta_w}x{delta_h}"
            )

            if abs(delta_w) <= 1 and abs(delta_h) <= 1:
                break

            outer = driver.get_window_size()
            next_width = max(100, int(outer.get("width", target_width)) + delta_w)
            next_height = max(100, int(outer.get("height", target_height)) + delta_h)
            driver.set_window_size(next_width, next_height)
            time.sleep(0.1)

        final_viewport = driver.execute_script(
            "return {"
            "  width: Math.floor(window.innerWidth || 0),"
            "  height: Math.floor(window.innerHeight || 0)"
            "};"
        )
        logger.info(
            "Final viewport size before screenshot: "
            f"{int(final_viewport.get('width', 0))}x{int(final_viewport.get('height', 0))}"
        )

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
