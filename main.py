#!/usr/bin/env python3
"""
Visual Testing Framework — Main entry point.

Usage examples
--------------
# Compare live screenshots against Figma designs (most common):
    python main.py --project qcflow --capture-screenshots

# Re-run comparison using already-captured screenshots (no network):
    python main.py --project qcflow

# Use the previous screenshot as the baseline instead of Figma:
    python main.py --project qcflow --baseline-mode screenshot --capture-screenshots

# High-DPI / retina screens (Chrome will report a 2880×1800 screenshot for a 1440×900 window):
    python main.py --project qcflow --dpr 2.0 --capture-screenshots

# Tighter threshold (99% similarity required):
    python main.py --project qcflow --threshold 0.99

# Fetch Figma JSON data (requires figma_access_token and figma_file_id in testcases.yaml):
    python main.py --project qcflow --fetch-figma
"""

import argparse
import sys
from pathlib import Path

from core.runner import TestRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Visual Testing Framework — compare UI screenshots against baselines.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # ── Required ──────────────────────────────────────────────────
    parser.add_argument(
        "--project", "-p",
        required=True,
        metavar="NAME",
        help="Sub-project folder name under projects/ (e.g. 'qcflow').",
    )

    # ── Baseline mode ─────────────────────────────────────────────
    parser.add_argument(
        "--baseline-mode",
        choices=["auto", "figma", "screenshot"],
        default="auto",
        help=(
            "Baseline image source for comparison.\n"
            "  auto       — first run uses Figma; if prior screenshots exist, uses previous screenshot (default).\n"
            "  figma      — always use Figma design images.\n"
            "  screenshot — use the previous captured screenshot;\n"
            "               falls back to Figma if no prior screenshot exists."
        ),
    )

    # ── Quality controls ──────────────────────────────────────────
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.90,
        metavar="FLOAT",
        help="Minimum SSIM similarity score to pass (0.0–1.0). Default: 0.90.",
    )
    parser.add_argument(
        "--max-diff-pct",
        type=float,
        default=0.005,
        metavar="FLOAT",
        help=(
            "Maximum allowed percentage of significantly-different pixels (0.0–1.0). "
            "E.g. 0.005 means fail if more than 0.5%% of pixels differ noticeably. "
            "Catches small localised changes (missing words, colour shifts) that barely "
            "affect the global SSIM. Default: 0.005."
        ),
    )
    parser.add_argument(
        "--diff-sensitivity",
        type=int,
        default=30,
        metavar="INT",
        help=(
            "Per-channel brightness delta (0–255) above which a pixel counts as "
            "'significantly different' for --max-diff-pct. Default: 30."
        ),
    )
    parser.add_argument(
        "--tile-threshold",
        type=float,
        default=0.85,
        metavar="FLOAT",
        help=(
            "Minimum SSIM score allowed for any single image tile (0.0–1.0). "
            "The image is divided into --tile-size × --tile-size tiles and SSIM "
            "is computed per tile. Fails when the worst tile falls below this "
            "value, catching small localised differences (missing text, icon "
            "changes) that barely affect the global score. Default: 0.85."
        ),
    )
    parser.add_argument(
        "--tile-size",
        type=int,
        default=200,
        metavar="INT",
        help="Side-length in pixels for tiled SSIM comparison. Default: 200.",
    )
    parser.add_argument(
        "--dpr",
        type=float,
        default=1.0,
        metavar="FLOAT",
        help=(
            "Device Pixel Ratio of the captured screenshots.\n"
            "Screenshots are scaled down by this factor before comparison.\n"
            "Use 2.0 for retina/HiDPI displays. Default: 1.0."
        ),
    )

    # ── Actions ───────────────────────────────────────────────────
    parser.add_argument(
        "--capture-screenshots",
        action="store_true",
        help="Capture fresh screenshots via Selenium before comparing.",
    )
    parser.add_argument(
        "--fetch-figma",
        action="store_true",
        help=(
            "Fetch Figma JSON file data for design analysis.\n"
            "Requires header-level figma_access_token and per-test\n"
            "figma_file_id in testcases.yaml. User must provide\n"
            "the expected Figma image in the figma folder."
        ),
    )

    # ── Browser options ───────────────────────────────────────────
    parser.add_argument(
        "--browser",
        choices=["chrome", "firefox", "edge"],
        default="chrome",
        help="Browser for Selenium screenshots. Default: chrome.",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Show the browser window (useful for debugging).",
    )
    parser.add_argument(
        "--page-load-timeout",
        type=int,
        default=300,
        metavar="SECONDS",
        help="Selenium page-load timeout in seconds. Default: 300.",
    )

    # ── Report ────────────────────────────────────────────────────
    parser.add_argument(
        "--report-name",
        default=None,
        metavar="FILENAME",
        help="Custom HTML report filename (e.g. 'run1.html'). Default: auto-timestamped.",
    )

    return parser


def validate_args(args, parser: argparse.ArgumentParser) -> None:
    if not 0.0 < args.threshold <= 1.0:
        parser.error(f"--threshold must be in (0.0, 1.0], got {args.threshold}")

    if args.max_diff_pct is not None and not 0.0 <= args.max_diff_pct <= 1.0:
        parser.error(f"--max-diff-pct must be in [0.0, 1.0], got {args.max_diff_pct}")

    if not 0 < args.diff_sensitivity <= 255:
        parser.error(f"--diff-sensitivity must be in (0, 255], got {args.diff_sensitivity}")

    if not 0.0 < args.tile_threshold <= 1.0:
        parser.error(f"--tile-threshold must be in (0.0, 1.0], got {args.tile_threshold}")

    if args.tile_size < 16:
        parser.error(f"--tile-size must be >= 16, got {args.tile_size}")

    if args.dpr <= 0:
        parser.error(f"--dpr must be positive, got {args.dpr}")

    if args.page_load_timeout <= 0:
        parser.error(
            f"--page-load-timeout must be positive, got {args.page_load_timeout}"
        )

    project_path = Path("projects") / args.project
    if not project_path.exists():
        available = (
            [d.name for d in Path("projects").iterdir() if d.is_dir()]
            if Path("projects").exists()
            else []
        )
        parser.error(
            f"Project '{args.project}' not found at '{project_path.resolve()}'.\n"
            f"Available projects: {available or 'none'}"
        )

    testcases_path = project_path / "testcases.yaml"
    if not testcases_path.exists():
        parser.error(f"testcases.yaml not found at '{testcases_path.resolve()}'")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    validate_args(args, parser)

    runner = TestRunner(
        project=args.project,
        baseline_mode=args.baseline_mode,
        threshold=args.threshold,
        max_diff_pct=args.max_diff_pct,
        diff_sensitivity=args.diff_sensitivity,
        tile_threshold=args.tile_threshold,
        tile_size=args.tile_size,
        dpr=args.dpr,
        capture_screenshots=args.capture_screenshots,
        fetch_figma=args.fetch_figma,
        headless=not args.no_headless,
        browser=args.browser,
        report_name=args.report_name,
        page_load_timeout=args.page_load_timeout,
    )

    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
