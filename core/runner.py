"""
Orchestrates the end-to-end visual test execution for a sub-project.
Logs all test lifecycle events, downloads, captures, and comparisons.
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml

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


@dataclass
class TestResult:
    test_case: TestCase
    status: str                          # 'passed' | 'failed' | 'skipped' | 'error'
    comparison: Optional[ComparisonResult] = None
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    baseline_path: Optional[str] = None


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

    def __init__(
        self,
        project: str,
        baseline_mode: str = "auto",
        threshold: float = 0.90,
        max_diff_pct: Optional[float] = 0.005,
        diff_sensitivity: int = 30,
        tile_threshold: float = 0.85,
        tile_size: int = 200,
        dpr: float = 1.0,
        capture_screenshots: bool = False,
        fetch_figma: bool = False,
        headless: bool = True,
        browser: str = "chrome",
        report_name: Optional[str] = None,
        page_load_wait: int = 3,
    ):
        self.project = project
        self.requested_baseline_mode = baseline_mode
        self.baseline_mode = baseline_mode
        self.threshold = threshold
        self.max_diff_pct = max_diff_pct
        self.diff_sensitivity = diff_sensitivity
        self.tile_threshold = tile_threshold
        self.tile_size = tile_size
        self.dpr = dpr
        self.capture_screenshots = capture_screenshots
        self.fetch_figma = fetch_figma
        self.headless = headless
        self.browser = browser
        self.report_name = report_name
        self.page_load_wait = page_load_wait
        self.run_mode = "selected"
        self.target_test_name: Optional[str] = None
        self.config_baseline_mode = "auto"

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
        for tc in test_cases:
            # In selected mode, keep disabled tests visible as skipped in report.
            if self.run_mode == "selected" and not tc.run:
                self._log(f"  [SKIP] {tc.name}  (run=false)")
                logger.info(f"Test skipped: {tc.name} (run=false)")
                results.append(TestResult(test_case=tc, status="skipped"))
                continue

            self._log(f"\n  [RUN]  {tc.name}  ({tc.device})  →  {tc.url}")
            logger.info(f"Running test: {tc.name} on {tc.device} device")
            result = self._run_single(tc)
            results.append(result)
            self._log_result(result)

        logger = get_logger("core.runner")
        report_path = ReportGenerator(
            project=self.project,
            project_path=self.project_path,
            reports_dir=self.reports_dir,
        ).generate(results, self.report_name)
        logger.info(f"HTML report generated: {report_path}")

        self._print_summary(results, report_path)
        success = all(r.status in ("passed", "skipped") for r in results)
        logger.info(f"Test run completed: success={success}")
        return success

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_test_cases(self) -> List[TestCase]:
        logger = get_logger("core.runner")
        path = self.project_path / "testcases.yaml"
        logger.debug(f"Loading test cases from: {path}")
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}

        global_figma_access_token = str(data.get("figma_access_token", "")).strip() or None

        raw_baseline_mode = str(data.get("baseline_mode", "auto")).strip().lower()
        if raw_baseline_mode not in {"auto", "figma", "screenshot"}:
            logger.warning(
                f"Invalid baseline_mode='{raw_baseline_mode}' in testcases.yaml; defaulting to 'auto'"
            )
            self.config_baseline_mode = "auto"
        else:
            self.config_baseline_mode = raw_baseline_mode

        raw_run_mode = str(data.get("run_mode", "selected")).strip()
        mode_lc = raw_run_mode.lower()
        if mode_lc == "all":
            self.run_mode = "all"
            self.target_test_name = None
        elif mode_lc == "selected" or not raw_run_mode:
            self.run_mode = "selected"
            self.target_test_name = None
        else:
            # Any non-reserved run_mode value is treated as a test name.
            self.run_mode = "test_name"
            self.target_test_name = raw_run_mode

        cases = []
        for raw in data.get("test_cases", []):
            raw_token = str(raw.get("figma_access_token", "")).strip() or None
            
            # Handle None values from YAML (e.g., `figma_file_id:` with no value)
            figma_file_id_raw = raw.get("figma_file_id")
            figma_file_id = None if figma_file_id_raw is None else str(figma_file_id_raw).strip() or None
            
            figma_node_id_raw = raw.get("figma_node_id")
            figma_node_id = "" if figma_node_id_raw is None else str(figma_node_id_raw).strip()
            
            cases.append(
                TestCase(
                    name=raw["name"],
                    run=raw.get("run", True),
                    device=raw.get("device", "Desktop"),
                    figma_file_name=raw.get(
                        "figma_file_name", f"{raw['name']}_figma.png"
                    ),
                    url=raw["url"],
                    figma_access_token=raw_token or global_figma_access_token,
                    figma_file_id=figma_file_id,
                    figma_node_id=figma_node_id,
                )
            )

        if self.run_mode == "test_name":
            filtered = [c for c in cases if c.name == self.target_test_name]
            if not filtered:
                available = ", ".join(c.name for c in cases) or "none"
                raise ValueError(
                    f"run_mode specifies test '{self.target_test_name}', but it was not found. "
                    f"Available tests: {available}"
                )
            logger.info(f"run_mode='{self.target_test_name}' -> executing exactly one test")
            return filtered

        logger.info(f"run_mode='{self.run_mode}'")
        return cases

    def _resolve_baseline_mode(self, test_cases: List[TestCase]) -> None:
        logger = get_logger("core.runner")
        if self.requested_baseline_mode != "auto":
            self.baseline_mode = self.requested_baseline_mode
            self._persist_baseline_mode_in_yaml(self.baseline_mode)
            return

        if self.config_baseline_mode in {"figma", "screenshot"}:
            self.baseline_mode = self.config_baseline_mode
            logger.info(f"baseline_mode from testcases.yaml: '{self.baseline_mode}'")
            return

        runnable_cases = test_cases
        if self.run_mode == "selected":
            runnable_cases = [tc for tc in test_cases if tc.run]

        has_previous_screenshots = any(
            self._latest_screenshot(tc.name) is not None for tc in runnable_cases
        )
        if not has_previous_screenshots:
            self.baseline_mode = "figma"
            logger.info("auto baseline mode: no prior screenshots found, using figma")
        else:
            self.baseline_mode = "screenshot"
            logger.info("auto baseline mode: prior screenshots found, using screenshot")
        self._persist_baseline_mode_in_yaml(self.baseline_mode)

    def _persist_baseline_mode_in_yaml(self, baseline_mode: str) -> None:
        """Persist baseline_mode in testcases.yaml while preserving existing comments."""
        logger = get_logger("core.runner")
        path = self.project_path / "testcases.yaml"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning(f"Could not read {path} to persist baseline_mode: {exc}")
            return

        lines = text.splitlines()
        baseline_pattern = re.compile(r"^(\s*)baseline_mode\s*:\s*.*$")
        run_mode_pattern = re.compile(r"^\s*run_mode\s*:\s*.*$")

        updated = False
        for idx, line in enumerate(lines):
            if baseline_pattern.match(line) and not line.lstrip().startswith("#"):
                lines[idx] = f"baseline_mode: '{baseline_mode}'"
                updated = True
                break

        if not updated:
            insert_idx = None
            for idx, line in enumerate(lines):
                if run_mode_pattern.match(line) and not line.lstrip().startswith("#"):
                    insert_idx = idx + 1
                    break

            new_line = f"baseline_mode: '{baseline_mode}'"
            if insert_idx is None:
                lines.insert(0, new_line)
            else:
                lines.insert(insert_idx, new_line)

        new_text = "\n".join(lines) + "\n"
        if new_text == text:
            return

        try:
            path.write_text(new_text, encoding="utf-8")
            logger.info(f"Persisted baseline_mode='{baseline_mode}' in {path.name}")
        except OSError as exc:
            logger.warning(f"Could not write {path} to persist baseline_mode: {exc}")

    @staticmethod
    def _prompt_baseline_choice() -> str:
        print("\nPrior screenshots were found for this project.")
        print("Choose baseline source for this run:")
        print("  1) Figma (user-provided image)")
        print("  2) Last execution screenshot")

        while True:
            choice = input("Enter choice [1/2 or figma/screenshot]: ").strip().lower()
            if choice in {"1", "figma", "f"}:
                return "figma"
            if choice in {"2", "screenshot", "s"}:
                return "screenshot"
            print("Invalid choice. Please enter 1/2, figma, or screenshot.")

    def _run_single(self, tc: TestCase) -> TestResult:
        device_cfg = self.DEVICE_CONFIGS.get(
            tc.device, self.DEVICE_CONFIGS["Desktop"]
        )
        screenshot_path: Optional[str] = None
        baseline_path: Optional[str] = None

        try:
            # ── Fetch Figma JSON data ──────────────────────────────────
            figma_path = self.figma_dir / tc.figma_file_name
            
            # Skip API call if figma_file_id is blank (None or empty string)
            has_file_id = tc.figma_file_id and str(tc.figma_file_id).strip()
            has_token = tc.figma_access_token and str(tc.figma_access_token).strip()
            
            if has_file_id and has_token:
                self._log("    ↳ Fetching Figma JSON data …")
                try:
                    FigmaClient(tc.figma_access_token).fetch_file_data(
                        file_id=tc.figma_file_id
                    )
                    self._log(f"    ↳ Figma JSON data fetched successfully")
                except Exception as exc:
                    logger.error(f"Failed to fetch Figma JSON data: {exc}")
                    return TestResult(
                        test_case=tc,
                        status="error",
                        error_message=f"Failed to fetch Figma JSON data: {exc}",
                    )
            elif has_file_id and not has_token:
                self._log(
                    "    ↳ Skipping Figma API call: figma_access_token is missing; "
                    "using provided local Figma image."
                )
            else:
                self._log(
                    "    ↳ Skipping Figma API call: figma_file_id is blank; "
                    "using provided local Figma image."
                )

            if not figma_path.exists():
                return TestResult(
                    test_case=tc,
                    status="error",
                    error_message=(
                        f"Figma image '{figma_path}' not found. "
                        "Provide this image file manually in the figma folder."
                    ),
                )

            # ── Capture screenshot ─────────────────────────────────────
            if self.capture_screenshots:
                self._log(
                    f"    ↳ Capturing screenshot "
                    f"({device_cfg['width']}×{device_cfg['height']}, "
                    f"DPR={self.dpr}) …"
                )
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = str(
                    self.screenshots_dir / f"{tc.name}_{ts}.png"
                )
                ScreenshotCapture(
                    browser=self.browser,
                    headless=self.headless,
                    dpr=self.dpr,
                    page_load_wait=self.page_load_wait,
                ).capture(
                    url=tc.url,
                    output_path=screenshot_path,
                    width=device_cfg["width"],
                    height=device_cfg["height"],
                )
                self._log(f"    ↳ Screenshot saved: {Path(screenshot_path).name}")

            # ── Determine baseline / actual paths ──────────────────────
            if self.baseline_mode == "figma":
                baseline_path = str(figma_path)
                if not screenshot_path:
                    screenshot_path = self._latest_screenshot(tc.name)
                if not screenshot_path:
                    return TestResult(
                        test_case=tc,
                        status="error",
                        error_message=(
                            "No screenshot available. "
                            "Run with --capture-screenshots first."
                        ),
                    )
                actual_path = screenshot_path

            else:  # baseline_mode == "screenshot"
                if not screenshot_path:
                    screenshot_path = self._latest_screenshot(tc.name)
                if not screenshot_path:
                    return TestResult(
                        test_case=tc,
                        status="error",
                        error_message="No screenshots available for comparison.",
                    )
                actual_path = screenshot_path

                baseline_path = self._previous_screenshot(tc.name, exclude=screenshot_path)
                if not baseline_path:
                    # Graceful fallback: use Figma image if available
                    if figma_path.exists():
                        baseline_path = str(figma_path)
                        self._log(
                            "    ↳ No previous screenshot found – "
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
            self._log("    ↳ Comparing images …")
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
            )

        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            return TestResult(
                test_case=tc,
                status="error",
                error_message=str(exc),
            )

    # ------------------------------------------------------------------
    # Screenshot helpers
    # ------------------------------------------------------------------

    def _latest_screenshot(self, test_name: str) -> Optional[str]:
        matches = sorted(
            self.screenshots_dir.glob(f"{test_name}_*.png"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return str(matches[0]) if matches else None

    def _previous_screenshot(
        self, test_name: str, exclude: str
    ) -> Optional[str]:
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
        mode_label = self.target_test_name if self.run_mode == "test_name" else self.run_mode
        print(f"  Run Mode: {mode_label}")
        print("=" * w)

    @staticmethod
    def _log_result(result: TestResult) -> None:
        icons = {"passed": "✓", "failed": "✗", "error": "!", "skipped": "-"}
        icon = icons.get(result.status, "?")
        line = f"  [{icon}] {result.test_case.name}: {result.status.upper()}"
        if result.comparison:
            line += f"  (SSIM {result.comparison.similarity:.4f})"
        if result.error_message:
            line += f"  — {result.error_message}"
        print(line)

    @staticmethod
    def _print_summary(results: List[TestResult], report_path: str) -> None:
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
        print("=" * w + "\n")
