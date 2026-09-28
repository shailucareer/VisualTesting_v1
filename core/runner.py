"""
Orchestrates the end-to-end visual test execution for a sub-project.
Logs all test lifecycle events, downloads, captures, and comparisons.
"""

import os
import csv
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PIL import Image

from .logging_config import get_logger, setup_logging
from .comparison import ComparisonResult, ImageComparator
from .figma_client import FigmaClient
from .reporter import ReportGenerator
from .screenshot import ScreenshotCapture

logger = get_logger("core.runner")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class TestCase:
    name: str
    run: bool
    device: str
    figma_file_name: str
    url: str
    figma_access_token: Optional[str] = None
    figma_file_id: Optional[str] = None
    figma_node_id: Optional[str] = None
    page_data_load_wait: int = 3


@dataclass
class TestResult:
    test_case: TestCase
    status: str                          # 'passed' | 'failed' | 'skipped' | 'error'
    comparison: Optional[ComparisonResult] = None
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    baseline_path: Optional[str] = None
    baseline_source: Optional[str] = None
    browser: Optional[str] = None


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class TestRunner:
    """
    Runs all enabled test cases in the given sub-project and produces a
    custom HTML report.

    Baseline modes
    --------------
    auto        – use Figma on first run; if prior screenshots exist, ask whether
                  to use Figma or previous screenshot as baseline.
    figma       – compare the live screenshot against the Figma design image.
    screenshot  – compare the latest screenshot against the *previous* one.
                  Falls back to the Figma image when no prior screenshot exists.
    """

    DEVICE_CONFIGS: dict = {
        "Desktop":       {"width": 1440, "height": 900},
        "Desktop Large": {"width": 1920, "height": 1080},
        "Tablet":        {"width": 768,  "height": 1024},
        "Mobile":        {"width": 375,  "height": 812},
        "Mobile Large":  {"width": 414,  "height": 896},
    }
    DEFAULT_PAGE_DATA_LOAD_WAIT = 3

    def __init__(
        self,
        project: str,
        baseline_mode: str = "auto",
        figma_access_token: Optional[str] = None,
        threshold: float = 0.90,
        max_diff_pct: Optional[float] = 0.005,
        diff_sensitivity: int = 30,
        tile_threshold: float = 0.85,
        tile_size: int = 200,
        dpr: float = 1.0,
        capture_screenshots: bool = False,
        fetch_figma: bool = False,
        headless: bool = True,
        browser: Optional[str] = None,
        browsers: Optional[List[str]] = None,
        report_name: Optional[str] = None,
        page_load_timeout: int = 60,
        match_figma_height: bool = False,
    ):
        self.project = project
        self.requested_baseline_mode = baseline_mode
        self.baseline_mode = baseline_mode
        self.figma_access_token = (
            str(figma_access_token).strip() or None
            if figma_access_token is not None
            else None
        )
        self.threshold = threshold
        self.max_diff_pct = max_diff_pct
        self.diff_sensitivity = diff_sensitivity
        self.tile_threshold = tile_threshold
        self.tile_size = tile_size
        self.dpr = dpr
        self.capture_screenshots = capture_screenshots
        self.match_figma_height = match_figma_height
        self.fetch_figma = fetch_figma
        self.headless = headless
        if browsers:
            self.browsers = list(browsers)
        else:
            self.browsers = [browser or "chrome"]
        self.browser = self.browsers[0]
        # For multi-browser runs, do not mix in legacy screenshots that lack browser suffixes.
        self.allow_legacy_screenshot_lookup = len(self.browsers) == 1
        self.report_name = report_name
        self.page_load_timeout = page_load_timeout

        self.project_path   = Path("projects") / project
        self.figma_dir      = self.project_path / "figma_images"
        self.screenshots_dir = self.project_path / "screenshots"
        self.reports_dir    = self.project_path / "reports"
        self.diffs_dir      = self.project_path / "diffs"

        for d in (self.figma_dir, self.screenshots_dir, self.reports_dir, self.diffs_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> bool:
        """Execute all test cases.  Returns True when all pass."""
        run_started_at = datetime.now()
        # Initialize logging for this project
        setup_logging(project=self.project)
        logger = get_logger("core.runner")

        logger.info(f"Starting visual tests for project: {self.project}")
        test_cases = self._load_test_cases()
        self._resolve_baseline_mode(test_cases)
        self._print_header()
        logger.debug(
            f"Configuration: requested_baseline_mode={self.requested_baseline_mode}, "
            f"effective_baseline_mode={self.baseline_mode}, threshold={self.threshold}, dpr={self.dpr}"
        )

        logger.info(f"Loaded {len(test_cases)} test case(s)")
        results: List[TestResult] = []

        logger = get_logger("core.runner")
        for browser in self.browsers:
            self.browser = browser
            if len(self.browsers) > 1:
                self._log(f"\n  [BROWSER] {browser}")
                logger.info(f"Running test set on browser: {browser}")

            for tc in test_cases:
                if not tc.run:
                    self._log(f"  [SKIP] {tc.name}  (run=false)")
                    logger.info(f"Test skipped: {tc.name} (run=false), browser={browser}")
                    results.append(TestResult(test_case=tc, status="skipped", browser=browser))
                    continue

                self._log(f"\n  [RUN]  {tc.name}  ({tc.device})  ->  {tc.url}  [browser={browser}]")
                logger.info(f"Running test: {tc.name} on {tc.device} device, browser={browser}")
                result = self._run_single(tc)
                results.append(result)
                self._log_result(result)

        logger = get_logger("core.runner")
        run_finished_at = datetime.now()
        runtime_seconds = max((run_finished_at - run_started_at).total_seconds(), 0.0)

        runtime_metadata = {
            "duration": self._format_duration(runtime_seconds),
            "duration_seconds": round(runtime_seconds, 3),
            "runtime_parameters": self._build_runtime_parameters(),
        }

        report_path = ReportGenerator(
            project=self.project,
            project_path=self.project_path,
            reports_dir=self.reports_dir,
        ).generate(results, self.report_name, runtime_metadata)
        logger.info(f"HTML report generated: {report_path}")
        history_path = str((self.reports_dir / "history.html").resolve())

        self._print_summary(results, report_path, history_path)
        success = all(r.status in ("passed", "skipped") for r in results)
        logger.info(f"Test run completed: success={success}")
        return success

    def _build_runtime_parameters(self) -> dict:
        """Build runtime parameters shown in report and history headers."""
        baseline_display = self.baseline_mode
        if self.requested_baseline_mode == "auto":
            baseline_display = f"{self.baseline_mode} (auto resolved at runtime)"

        params = OrderedDict()
        params["baseline_mode"] = baseline_display
        params["project"] = self.project
        params["threshold"] = self.threshold
        params["max_diff_pct"] = self.max_diff_pct
        params["diff_sensitivity"] = self.diff_sensitivity
        params["tile_threshold"] = self.tile_threshold
        params["tile_size"] = self.tile_size
        params["dpr"] = self.dpr
        params["capture_screenshots"] = self.capture_screenshots
        params["match_figma_height"] = self.match_figma_height
        params["fetch_figma"] = self.fetch_figma
        params["headless"] = self.headless
        params["browser"] = ", ".join(self.browsers)
        params["page_load_timeout"] = self.page_load_timeout
        return params

    @staticmethod
    def _format_duration(duration_seconds: float) -> str:
        """Format duration in HH:MM:SS.mmm format."""
        total_ms = int(round(duration_seconds * 1000))
        hours = total_ms // 3_600_000
        remaining = total_ms % 3_600_000
        minutes = remaining // 60_000
        remaining = remaining % 60_000
        seconds = remaining // 1000
        milliseconds = remaining % 1000
        return f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_test_cases(self) -> List[TestCase]:
        logger = get_logger("core.runner")
        path = self.project_path / "testcases.csv"
        logger.debug(f"Loading test cases from: {path}")
        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = reader.fieldnames or []
            required_columns = ["name", "run", "device", "figma_file_name", "url"]
            missing_columns = [column for column in required_columns if column not in fieldnames]
            if missing_columns:
                raise ValueError(
                    f"testcases.csv is missing required column(s): {', '.join(missing_columns)}"
                )

            cases = []
            for row_number, raw in enumerate(reader, start=2):
                if not any((value or "").strip() for value in raw.values()):
                    continue

                name = (raw.get("name") or "").strip()
                url = (raw.get("url") or "").strip()
                if not name:
                    raise ValueError(f"testcases.csv row {row_number} is missing 'name'")
                if not url:
                    raise ValueError(
                        f"testcases.csv row {row_number} for test '{name}' is missing 'url'"
                    )

                figma_file_name = (raw.get("figma_file_name") or "").strip() or f"{name}_figma.png"
                figma_file_id = (raw.get("figma_file_id") or "").strip() or None
                figma_node_id = (raw.get("figma_node_id") or "").strip()
                raw_page_data_load_wait = raw.get(
                    "page_data_load_wait", self.DEFAULT_PAGE_DATA_LOAD_WAIT
                )
                page_data_load_wait = self._parse_wait_seconds(
                    raw_page_data_load_wait,
                    default=self.DEFAULT_PAGE_DATA_LOAD_WAIT,
                    field_name="page_data_load_wait",
                    test_case_name=name,
                )

                cases.append(
                    TestCase(
                        name=name,
                        run=self._parse_run_flag(
                            raw.get("run"), row_number=row_number, test_case_name=name
                        ),
                        device=(raw.get("device") or "Desktop").strip() or "Desktop",
                        figma_file_name=figma_file_name,
                        url=url,
                        figma_access_token=self.figma_access_token,
                        figma_file_id=figma_file_id,
                        figma_node_id=figma_node_id,
                        page_data_load_wait=page_data_load_wait,
                    )
                )

        if not cases:
            logger.warning(f"No test cases found in {path}")
        return cases

    def _resolve_baseline_mode(self, test_cases: List[TestCase]) -> None:
        logger = get_logger("core.runner")
        if self.requested_baseline_mode != "auto":
            self.baseline_mode = self.requested_baseline_mode
            return

        runnable_cases = [tc for tc in test_cases if tc.run] or test_cases
        has_previous_screenshots = any(
            any(self._latest_screenshot(tc.name, browser=b) is not None for b in self.browsers)
            for tc in runnable_cases
        )
        if not has_previous_screenshots:
            self.baseline_mode = "figma"
            logger.info("auto baseline mode: no prior screenshots found, using figma")
        else:
            self.baseline_mode = "screenshot"
            logger.info("auto baseline mode: prior screenshots found, using screenshot")

    def _run_single(self, tc: TestCase) -> TestResult:
        device_cfg = self.DEVICE_CONFIGS.get(
            tc.device, self.DEVICE_CONFIGS["Desktop"]
        )
        screenshot_path: Optional[str] = None
        baseline_path: Optional[str] = None

        try:
            # ── Fetch Figma data / exports (optional) ──────────────────
            figma_path = self.figma_dir / tc.figma_file_name
            fetched_figma_path: Optional[Path] = None

            # Skip API call if figma_file_id is blank (None or empty string)
            has_file_id = tc.figma_file_id and str(tc.figma_file_id).strip()
            has_node_id = tc.figma_node_id and str(tc.figma_node_id).strip()
            has_token = tc.figma_access_token and str(tc.figma_access_token).strip()

            if self.fetch_figma:
                if not has_file_id:
                    self._log(
                        "    -> Skipping Figma fetch: figma_file_id is blank; "
                        "using local Figma image if available."
                    )
                elif not has_token:
                    return TestResult(
                        test_case=tc,
                        status="error",
                        error_message=(
                            "--fetch-figma was requested but figma_access_token is missing."
                        ),
                    )
                else:
                    self._log("    -> Fetching Figma JSON data...")
                    client = FigmaClient(tc.figma_access_token)
                    try:
                        client.fetch_file_data(file_id=tc.figma_file_id)
                        self._log("    -> Figma JSON data fetched successfully")
                    except Exception as exc:
                        logger.error(f"Failed to fetch Figma JSON data: {exc}")
                        return TestResult(
                            test_case=tc,
                            status="error",
                            error_message=f"Failed to fetch Figma JSON data: {exc}",
                        )

                    if self.baseline_mode == "figma":
                        if not has_node_id:
                            return TestResult(
                                test_case=tc,
                                status="error",
                                error_message=(
                                    "baseline_mode=figma with --fetch-figma requires "
                                    "figma_node_id in testcases.csv"
                                ),
                            )
                        try:
                            fetched_name = f"{tc.name}_figma_api.png"
                            fetched_figma_path = self.figma_dir / fetched_name
                            client.download_node_image(
                                file_id=tc.figma_file_id,
                                node_id=tc.figma_node_id,
                                output_path=str(fetched_figma_path),
                            )
                            self._log(
                                f"    -> Figma node image downloaded: {fetched_name}"
                            )
                        except Exception as exc:
                            logger.error(f"Failed to download Figma node image: {exc}")
                            return TestResult(
                                test_case=tc,
                                status="error",
                                error_message=f"Failed to download Figma node image: {exc}",
                            )

            baseline_image_path = fetched_figma_path if fetched_figma_path else figma_path

            # ── Capture screenshot ─────────────────────────────────────
            if self.capture_screenshots:
                figma_image_width = None
                figma_image_height = None
                try:
                    with Image.open(baseline_image_path) as figma_img:
                        figma_image_width = figma_img.width
                        figma_image_height = figma_img.height
                except Exception as exc:
                    self._log(
                        f"    -> Could not read baseline image size ({exc}); "
                        "continuing with page/default capture size."
                    )

                self._log(
                    f"    -> Capturing screenshot "
                    f"({device_cfg['width']}x{device_cfg['height']}, "
                    f"DPR={self.dpr})..."
                )
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = str(
                    self.screenshots_dir / f"{tc.name}_{self.browser}_{ts}.png"
                )
                ScreenshotCapture(
                    browser=self.browser,
                    headless=self.headless,
                    dpr=self.dpr,
                    page_load_timeout=self.page_load_timeout,
                    page_data_load_wait=tc.page_data_load_wait,
                ).capture(
                    url=tc.url,
                    output_path=screenshot_path,
                    width=device_cfg["width"],
                    height=device_cfg["height"],
                    figma_image_width=figma_image_width,
                    figma_image_height=figma_image_height,
                    match_figma_height=self.match_figma_height,
                )
                self._log(f"    -> Screenshot saved: {Path(screenshot_path).name}")

            # ── Determine baseline / actual paths ──────────────────────
            if self.baseline_mode == "figma":
                if not baseline_image_path.exists():
                    return TestResult(
                        test_case=tc,
                        status="error",
                        error_message=(
                            f"Figma baseline image '{baseline_image_path}' not found. "
                            "Either provide local image in figma_images or run with "
                            "--fetch-figma plus figma_file_id and figma_node_id."
                        ),
                    )
                baseline_path = str(baseline_image_path)
                if not screenshot_path:
                    screenshot_path = self._latest_screenshot(tc.name, browser=self.browser)
                if not screenshot_path:
                    return TestResult(
                        test_case=tc,
                        status="error",
                        browser=self.browser,
                        error_message=(
                            "No screenshot available. "
                            "Run with --capture-screenshots first."
                        ),
                    )
                actual_path = screenshot_path

            else:  # baseline_mode == "screenshot"
                if not screenshot_path:
                    screenshot_path = self._latest_screenshot(tc.name, browser=self.browser)
                if not screenshot_path:
                    return TestResult(
                        test_case=tc,
                        status="error",
                        browser=self.browser,
                        error_message="No screenshots available for comparison. Run with --capture-screenshots",
                    )
                actual_path = screenshot_path

                baseline_path = self._previous_screenshot(
                    tc.name,
                    exclude=screenshot_path,
                    browser=self.browser,
                )
                if not baseline_path:
                    # Graceful fallback: use Figma image if available
                    if baseline_image_path.exists():
                        baseline_path = str(baseline_image_path)
                        self._log(
                            "    -> No previous screenshot found - "
                            "using Figma image as baseline."
                        )
                    else:
                        return TestResult(
                            test_case=tc,
                            status="error",
                            error_message=(
                                "No baseline available: no previous screenshot "
                                "and no Figma image on disk."
                            ),
                        )

            # ── Image comparison ───────────────────────────────────────
            self._log("    -> Comparing images...")
            diff_dir = str(self.diffs_dir / tc.name)
            comparison = ImageComparator(
                threshold=self.threshold,
                dpr=self.dpr,
                max_diff_pct=self.max_diff_pct,
                diff_sensitivity=self.diff_sensitivity,
                tile_threshold=self.tile_threshold,
                tile_size=self.tile_size,
            ).compare(
                baseline_path=baseline_path,
                actual_path=actual_path,
                output_folder=diff_dir,
                test_name=tc.name,
            )

            return TestResult(
                test_case=tc,
                status="passed" if comparison.passed else "failed",
                comparison=comparison,
                screenshot_path=actual_path,
                baseline_path=baseline_path,
                baseline_source=baseline_source,
                browser=self.browser,
            )

        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            return TestResult(
                test_case=tc,
                status="error",
                error_message=str(exc),
                browser=self.browser,
            )

    def _parse_wait_seconds(
        self,
        value,
        *,
        default: int,
        field_name: str,
        test_case_name: str,
    ) -> int:
        """
        Parse wait seconds from CSV.

        Blank/missing values fall back to *default*. Invalid/non-positive values
        are ignored with a warning and also fall back to *default*.
        """
        if value is None:
            return default

        if isinstance(value, str) and not value.strip():
            return default

        try:
            parsed = int(value)
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid {field_name}='{value}' for test '{test_case_name}'. "
                f"Defaulting to {default}s"
            )
            return default

        if parsed < 0:
            logger.warning(
                f"Negative {field_name}='{value}' for test '{test_case_name}'. "
                f"Defaulting to {default}s"
            )
            return default

        return parsed

    def _parse_run_flag(self, value, *, row_number: int, test_case_name: str) -> bool:
        """Parse the CSV run flag into a boolean."""
        if value is None:
            return True

        normalized = str(value).strip().lower()
        if not normalized:
            return True
        if normalized in {"y", "yes", "true", "1"}:
            return True
        if normalized in {"n", "no", "false", "0"}:
            return False

        logger.warning(
            f"Invalid run='{value}' in testcases.csv row {row_number} for test '{test_case_name}'. "
            "Defaulting to disabled."
        )
        return False

    # ------------------------------------------------------------------
    # Screenshot helpers
    # ------------------------------------------------------------------

    def _latest_screenshot(self, test_name: str, browser: Optional[str] = None) -> Optional[str]:
        browser_name = browser or self.browser
        matches = sorted(
            self.screenshots_dir.glob(f"{test_name}_{browser_name}_*.png"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not matches and self.allow_legacy_screenshot_lookup:
            matches = sorted(
                self.screenshots_dir.glob(f"{test_name}_*.png"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        return str(matches[0]) if matches else None

    def _previous_screenshot(
        self, test_name: str, exclude: str, browser: Optional[str] = None
    ) -> Optional[str]:
        browser_name = browser or self.browser
        matches = sorted(
            (
                p for p in self.screenshots_dir.glob(f"{test_name}_{browser_name}_*.png")
                if str(p) != exclude
            ),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not matches and self.allow_legacy_screenshot_lookup:
            matches = sorted(
                (
                    p for p in self.screenshots_dir.glob(f"{test_name}_*.png")
                    if str(p) != exclude
                ),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        return str(matches[0]) if matches else None

    # ------------------------------------------------------------------
    # Logging / printing
    # ------------------------------------------------------------------

    @staticmethod
    def _log(msg: str) -> None:
        print(msg)

    def _print_header(self) -> None:
        w = 62
        print("\n" + "=" * w)
        print(f"  Visual Testing  |  Project: {self.project}")
        print(f"  Baseline: {self.baseline_mode:<10}  Threshold: {self.threshold}  DPR: {self.dpr}")
        print("=" * w)

    @staticmethod
    def _log_result(result: TestResult) -> None:
        icons = {"passed": "PASS", "failed": "FAIL", "error": "ERR", "skipped": "SKIP"}
        icon = icons.get(result.status, "?")
        browser_label = f" [{result.browser}]" if result.browser else ""
        line = f"  [{icon}] {result.test_case.name}{browser_label}: {result.status.upper()}"
        if result.comparison:
            line += f"  (SSIM {result.comparison.similarity:.4f})"
        if result.error_message:
            line += f"  - {result.error_message}"
        print(line)

    @staticmethod
    def _print_summary(results: List[TestResult], report_path: str, history_path: str) -> None:
        passed  = sum(1 for r in results if r.status == "passed")
        failed  = sum(1 for r in results if r.status == "failed")
        skipped = sum(1 for r in results if r.status == "skipped")
        errors  = sum(1 for r in results if r.status == "error")
        total   = len(results)
        w = 62
        print("\n" + "=" * w)
        print(
            f"  Results: {passed} passed  {failed} failed  "
            f"{skipped} skipped  {errors} errors  /  {total} total"
        )
        print(f"  Report : {report_path}")
        print(f"  History: {history_path}")
        print("=" * w + "\n")
