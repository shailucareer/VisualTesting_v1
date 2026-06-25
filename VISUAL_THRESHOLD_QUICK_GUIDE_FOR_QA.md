# Visual Comparison Thresholds: Quick Guide for QA

This guide explains, in simple terms, how PASS and FAIL are decided in this framework and how to tune thresholds safely.

## 1) How PASS/FAIL Works

One test passes only when all 3 checks pass:

```text
global_ssim      >= threshold
diff_pixels_pct  <= max_diff_pct
worst_tile_ssim  >= tile_threshold
```

Meaning:

- If even 1 check fails, final result is FAIL.
- This is expected behavior (not a bug).

Default values used by current implementation:

- --threshold 0.90
- --max-diff-pct 0.005 (0.5%)
- --diff-sensitivity 30
- --tile-threshold 0.85
- --tile-size 200

## 2) What Each Check Is Good At

Global SSIM (threshold):

- Good for large layout/structure changes.
- Can miss very small but important local UI issues.

Pixel-diff % (max-diff-pct + diff-sensitivity):

- Good for text/color/content shifts.
- diff-sensitivity controls how big a color/brightness change is counted as a "different pixel".

Worst-tile SSIM (tile-threshold + tile-size):

- Good for localized regressions (missing icon, wrong label, broken button).
- Smaller tile-size means stricter local detection.

## 3) Simple Example (Why 1 High SSIM Can Still FAIL)

```text
Global SSIM       = 0.97  (passes 0.90)
Diff pixels       = 0.90% (fails 0.50%)
Worst tile SSIM   = 0.72  (fails 0.85)
Final verdict     = FAIL
```

This is correct and intentional.

## 4) Ready-to-Use Command Profiles

Use these as starting points.

Balanced (recommended first run):

```bash
python main.py --project opinion_route --capture-screenshots
```

Permissive (fewer false failures while project stabilizes):

```bash
python main.py --project opinion_route --capture-screenshots --threshold 0.85 --max-diff-pct 0.02 --tile-threshold 0.80
```

Strict (for release sign-off checks):

```bash
python main.py --project opinion_route --capture-screenshots --threshold 0.95 --max-diff-pct 0.002 --tile-threshold 0.90
```

High-DPI display (retina-like systems):

```bash
python main.py --project opinion_route --capture-screenshots --dpr 2.0
```

## 5) Junior QA Quick Troubleshooting

Case A: "Result passed, but I can still see a visual issue"

1. Increase --threshold (example: 0.90 -> 0.93).
2. Decrease --max-diff-pct (example: 0.005 -> 0.003).
3. Increase --tile-threshold (example: 0.85 -> 0.88).
4. Reduce --tile-size (example: 200 -> 120) to catch smaller local problems.

Case B: "Result failed, but change is acceptable"

1. Decrease --threshold slightly.
2. Increase --max-diff-pct slightly.
3. Decrease --tile-threshold slightly.
4. Keep browser and DPR consistent between runs.

Case C: "Page looked incomplete in screenshot"

1. Increase page_data_load_wait for that test in testcases.yaml.
2. If navigation itself times out, increase --page-load-timeout.

Example test case setting in testcases.yaml:

```yaml
test_cases:
  - name: desktop_home
    run: true
    device: Desktop
    url: https://example.com
    figma_file_name: desktop_home.png
    page_data_load_wait: 8
```

Case D: "Headless browser is unstable"

1. Try Firefox: --browser firefox
2. Or run visible browser: --no-headless

## 6) Common QA Notes

- --fetch-figma fetches only Figma file JSON metadata.
- Baseline PNG files must already exist in projects/<project>/figma_images/.
- baseline_mode auto is non-interactive:
	- No previous screenshot -> figma
	- Previous screenshot exists -> screenshot
- Console output now prints absolute clickable paths for:
	- generated report.html
	- reports/history.html

Last updated: June 25, 2026
