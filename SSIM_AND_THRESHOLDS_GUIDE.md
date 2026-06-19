# SSIM, Pixel-Diff & Tile Threshold Guide

A comprehensive reference for understanding the framework's three comparison algorithms, thresholds, and run configurations.

## Table of Contents

1. [Algorithms Explained](#algorithms-explained)
2. [Thresholds Explained](#thresholds-explained)
3. [Why SSIM Alone Is Not Enough](#why-ssim-alone-is-not-enough)
4. [Run Commands Reference](#run-commands-reference)
5. [Common Scenarios](#common-scenarios)
6. [Troubleshooting](#troubleshooting)

---

## Algorithms Explained

The framework now uses **three independent checks**. A test fails if **any one** fails.

1. **Global SSIM** (scikit-image)
2. **Pixel-Diff Percentage** (significant-difference pixel ratio)
3. **Worst-Tile SSIM** (localized SSIM on image tiles)

This design prevents false passes where a small but important UI region differs (for example, missing text like "QA").

### 1) Global SSIM

**SSIM (Structural Similarity Index Metric)** is a mathematical algorithm that measures how similar two images are to each other.

### How SSIM Works

Instead of crude pixel-by-pixel comparison, SSIM analyzes **three key aspects**:

1. **Luminance (L)** — Overall brightness of the images
2. **Contrast (C)** — Variation in pixel intensity values
3. **Structure (S)** — Patterns, edges, and spatial relationships

### SSIM Score Range

SSIM produces a score between **0.0 and 1.0**:

| Score Range | Interpretation | Examples |
|-------------|----------------|----------|
| **1.0** | Identical images | Same screenshot, same conditions |
| **0.95–0.99** | Virtually identical | Minor anti-aliasing, font rendering |
| **0.90–0.94** | Very similar | Slight color shifts, minor layout changes |
| **0.85–0.89** | Similar with noticeable differences | Button moved, color changed significantly |
| **0.75–0.84** | Significant differences | Multiple layout changes, text repositioned |
| **< 0.75** | Major visual changes | Completely different layout or missing elements |

### 2) Pixel-Diff Percentage

This metric counts the percentage of pixels where at least one channel exceeds a configured difference threshold.

- Controlled by `--max-diff-pct` (default `0.005`, i.e. 0.5%)
- Sensitivity controlled by `--diff-sensitivity` (default `30`)

Useful for subtle but real visual mismatches.

### 3) Worst-Tile SSIM

The image is split into square tiles and SSIM is computed per tile.

- Controlled by `--tile-threshold` (default `0.85`)
- Tile granularity controlled by `--tile-size` (default `200` px)

If one tile has a major local change, the test fails even if global SSIM is high.

### Why This Hybrid Approach?

- **Pixel-perfect matching fails** when:
  - Font rendering differs (OS/browser differences)
  - JPEG compression varies
  - Sub-pixel anti-aliasing changes
  - Minor color shifts occur from browser rendering

- **Global SSIM** catches broad layout/structure regressions
- **Pixel-Diff %** catches fine-grained content/color changes
- **Worst-Tile SSIM** catches localized defects that global averaging hides

---

## Thresholds Explained

The framework applies pass/fail logic as:

```
PASS only if:
  global_ssim      >= threshold
  diff_pixels_pct  <= max_diff_pct
  worst_tile_ssim  >= tile_threshold
```

### Default Thresholds

- `--threshold 0.90` (minimum global SSIM)
- `--max-diff-pct 0.005` (max 0.5% significant pixels)
- `--diff-sensitivity 30` (channel delta for significant pixel)
- `--tile-threshold 0.85` (minimum SSIM for any tile)
- `--tile-size 200` (tile dimensions)

### Common Tuning Values

| Setting | Permissive | Default | Strict | Purpose |
|---------|------------|---------|--------|---------|
| `--threshold` | 0.85 | 0.90 | 0.95+ | Global structure similarity |
| `--max-diff-pct` | 0.02 | 0.005 | 0.001 | Significant pixel tolerance |
| `--tile-threshold` | 0.80 | 0.85 | 0.90+ | Localized SSIM floor |
| `--tile-size` | 300 | 200 | 120 | Localization granularity |

---

## Why SSIM Alone Is Not Enough

This was the most common issue in SSIM-only setups.

### Key Reason: Global Averaging Dilutes Local Defects

Global SSIM averages similarity over the full frame. A small missing string, icon, or badge can occupy <1% of pixels and still yield a high global score.

### Example

```
Global SSIM       = 0.97  (passes 0.90)
Diff pixels       = 0.9%  (fails 0.5%)
Worst tile SSIM   = 0.72  (fails 0.85)
Final verdict     = FAIL
```

This is exactly the behavior needed for localized regressions.

---

### Visual Inspection Still Matters

**Remember:** metrics provide automated guardrails, but human review is still valuable.

Always:
1. ✅ Check the **diff image** in the HTML report
2. ✅ Review the **side-by-side comparison**
3. ✅ Use the **interactive slider** to inspect changes closely
4. ✅ Make a human judgment call

---

## Run Commands Reference

### Basic Runs

#### 1. Compare with Default Settings (Figma baseline)
```bash
python main.py --project opinion_route
```
**Does:**
- Uses existing Figma images in `figma_images/` folder
- Compares against stored screenshots
- Uses default threshold: 0.90

**Output:** Report in `projects/opinion_route/reports/report_<timestamp>/`

---

#### 2. Capture Fresh Screenshots (Current State)
```bash
python main.py --project opinion_route --capture-screenshots
```
**Does:**
- Captures fresh screenshots via Selenium (opens browser)
- Compares against Figma baseline images
- Saves new screenshots to `screenshots/` folder
- Uses threshold: 0.90

**Output:** New screenshots + report

---

#### 3. Fetch Fresh Figma Metadata
```bash
python main.py --project opinion_route --fetch-figma
```
**Does:**
- Fetches latest Figma file metadata
- Compares against previously captured screenshots
- Credentials required in `testcases.yaml`
- Uses threshold: 0.90

**Output:** Updated Figma images + report

---

#### 4. Full Run (Figma metadata + Screenshots + Compare)
```bash
python main.py --project opinion_route --fetch-figma --capture-screenshots
```
**Does:**
- Downloads fresh Figma images
- Captures fresh screenshots
- Compares both
- Updates everything

**Output:** New images + comprehensive report

---

### Advanced Runs with Threshold Adjustments

#### 5. Very Strict Threshold (99% Similarity)
```bash
python main.py --project opinion_route --threshold 0.99 --capture-screenshots
```
**Does:**
- Captures screenshots
- Requires 99% match (only 1% difference acceptable)
- Stricter pass/fail criteria

**Use case:** Design systems, pixel-perfect requirements

---

#### 6. Permissive Threshold (85% Similarity)
```bash
python main.py --project opinion_route --threshold 0.85 --capture-screenshots
```
**Does:**
- Captures screenshots
- Allows up to 15% mathematical difference
- More forgiving of rendering variations

**Use case:** Dynamic content, experimental UIs

---

#### 7. Custom Threshold (92% Similarity)
```bash
python main.py --project opinion_route --threshold 0.92 --capture-screenshots
```
**Does:**
- Captures screenshots
- Allows up to 8% difference (middle ground)

**Use case:** Balanced approach for most projects

---

#### 8. Strict Local Difference Detection
```bash
python main.py --project opinion_route --max-diff-pct 0.002 --tile-threshold 0.90 --capture-screenshots
```
**Does:**
- Fails if >0.2% pixels differ significantly
- Fails if any tile drops below 90% SSIM

**Use case:** Catch missing words/icons and small visual defects

---

#### 9. Tune Pixel Sensitivity
```bash
python main.py --project opinion_route --diff-sensitivity 20 --capture-screenshots
```
**Does:**
- Counts smaller channel differences as significant
- Increases sensitivity to subtle color/text changes

---

#### 10. Higher Tile Granularity
```bash
python main.py --project opinion_route --tile-size 120 --capture-screenshots
```
**Does:**
- Creates smaller tiles
- Increases localization precision

---

### Baseline Mode Variations

#### 11. Compare Against Previous Screenshot (Regression Testing)
```bash
python main.py --project opinion_route --baseline-mode screenshot --capture-screenshots
```
**Does:**
- Uses **previous screenshot** as baseline (not Figma)
- Captures new screenshot
- Compares new vs. previous
- Falls back to Figma if no previous screenshot exists

**Use case:** Week-to-week regression detection, API-driven UIs

---

#### 12. Compare Against Figma Explicitly
```bash
python main.py --project opinion_route --baseline-mode figma --capture-screenshots
```
**Does:**
- Uses Figma images as baseline (explicitly set)
- Captures screenshots
- Compares screenshots vs. Figma

**Use case:** Design compliance verification

---

### Device Pixel Ratio (Retina/High-DPI)

#### 13. Capture for Retina Display (2x Scale)
```bash
python main.py --project opinion_route --dpr 2.0 --capture-screenshots
```
**Does:**
- Captures at 2x device pixel ratio
- Downscales to compare with baseline
- Better for high-DPI monitors

**Use case:** Retina MacBooks, high-DPI Linux displays, 2K/4K monitors

---

#### 14. Capture for Ultra-High DPI (2.5x Scale)
```bash
python main.py --project opinion_route --dpr 2.5 --capture-screenshots
```
**Does:**
- Captures at 2.5x device pixel ratio
- Useful for testing on 4K displays

**Use case:** Ultra-high resolution displays

---

### Browser Selection

#### 15. Use Firefox Instead of Chrome
```bash
python main.py --project opinion_route --browser firefox --capture-screenshots
```
**Does:**
- Captures screenshots using Firefox
- Default is Chrome

**Use case:** Firefox-specific rendering testing

---

#### 16. Use Edge Browser
```bash
python main.py --project opinion_route --browser edge --capture-screenshots
```
**Does:**
- Captures screenshots using Edge
- Chromium-based

**Use case:** Edge-specific compatibility testing

---

### Debug and Headless Mode

#### 17. Show Browser Window (Debugging)
```bash
python main.py --project opinion_route --no-headless --capture-screenshots
```
**Does:**
- Opens browser window visibly
- Slower (real rendering)
- Useful for debugging

**Use case:** Troubleshooting screenshot capture, debugging selectors

---

#### 18. Headless Mode (Default, Faster)
```bash
python main.py --project opinion_route --capture-screenshots
```
**Does:**
- Runs in headless mode (no visible browser)
- Faster performance
- Default behavior

**Use case:** CI/CD pipelines, batch testing

---

### Page Load Timing

#### 19. Increase Wait Time After Page Load
```bash
python main.py --project opinion_route --page-load-wait 5 --capture-screenshots
```
**Does:**
- Waits 5 seconds after page load (default: 3 seconds)
- Allows animations/transitions to complete

**Use case:** Heavy JavaScript, animations, lazy loading

---

#### 20. Minimal Wait Time
```bash
python main.py --project opinion_route --page-load-wait 1 --capture-screenshots
```
**Does:**
- Waits only 1 second after page load
- Faster, but may catch incomplete renders

**Use case:** Simple, static pages

---

### Custom Report Names

#### 21. Custom Report Filename
```bash
python main.py --project opinion_route --report-name "pre-launch-qa" --capture-screenshots
```
**Does:**
- Generates report with custom name: `pre-launch-qa/report.html`

**Use case:** Organized testing phases

---

#### 22. Timestamped Custom Report
```bash
python main.py --project opinion_route --report-name "sprint-42-final" --capture-screenshots
```
**Output:** `sprint-42-final/report.html` (no auto-timestamp added)

---

## Common Scenarios

### Scenario 1: Daily Regression Testing

**Goal:** Quick check for obvious visual regressions

```bash
python main.py --project opinion_route --capture-screenshots
```

**Why:** Default threshold (0.90) catches major changes; quick execution.

---

### Scenario 2: Pre-Release QA (Strict)

**Goal:** Ensure design compliance before launch

```bash
python main.py --project opinion_route --threshold 0.98 --max-diff-pct 0.002 --tile-threshold 0.90 --fetch-figma --capture-screenshots
```

**Why:** Strict global + local checks with fresh baseline context.

---

### Scenario 3: Multi-Browser Testing

**Goal:** Test across different browsers

```bash
# Chrome
python main.py --project opinion_route --browser chrome --capture-screenshots

# Firefox
python main.py --project opinion_route --browser firefox --capture-screenshots

# Edge
python main.py --project opinion_route --browser edge --capture-screenshots
```

**Why:** Browser rendering differs; test each independently.

---

### Scenario 4: Retina/High-DPI Testing

**Goal:** Ensure quality on high-resolution displays

```bash
python main.py --project opinion_route --dpr 2.0 --capture-screenshots
```

**Why:** DPR scaling prevents false positives on Retina displays.

---

### Scenario 5: Week-to-Week Regression (vs. Previous Screenshot)

**Goal:** Detect changes since last week

```bash
python main.py --project opinion_route --baseline-mode screenshot --capture-screenshots
```

**Why:** Compares new screenshot vs. previous (not Figma).

---

### Scenario 6: Debugging Failed Test

**Goal:** Understand why a test is failing

```bash
python main.py --project opinion_route --no-headless --page-load-wait 5 --threshold 0.99 --capture-screenshots
```

**Why:**
- `--no-headless` → See what the browser is doing
- `--page-load-wait 5` → Wait for all assets to load
- `--threshold 0.99` → Strict mode to see exact differences

---

### Scenario 7: Permissive Testing (Experimental UI)

**Goal:** Allow for rendering variations, focus on major changes

```bash
python main.py --project opinion_route --threshold 0.85 --max-diff-pct 0.02 --tile-threshold 0.80 --capture-screenshots
```

**Why:** Looser global and local gates allow expected experimental variance.

---

## Troubleshooting

### Problem: Test passes but I see visible differences

**Solution 1: Tighten all three gates**
```bash
python main.py --project opinion_route --threshold 0.95 --max-diff-pct 0.002 --tile-threshold 0.90 --capture-screenshots
```

**Solution 2: Inspect the diff image**
- Open the HTML report
- Use the interactive slider to zoom into differences
- Decide if they're acceptable

---

### Problem: Test fails but differences look minor

**Solution 1: Relax one or more gates**
```bash
python main.py --project opinion_route --threshold 0.88 --max-diff-pct 0.01 --tile-threshold 0.82 --capture-screenshots
```

**Solution 2: Check DPR setting**
If on Retina display:
```bash
python main.py --project opinion_route --dpr 2.0 --capture-screenshots
```

---

### Problem: Font rendering looks different across browsers

**Solution: Test both browsers**
```bash
# Chrome
python main.py --project opinion_route --browser chrome --capture-screenshots

# Firefox
python main.py --project opinion_route --browser firefox --capture-screenshots
```

Then compare SSIM scores. Small differences (~0.91-0.95) are normal.

---

### Problem: Screenshots capture before page is fully loaded

**Solution: Increase wait time**
```bash
python main.py --project opinion_route --page-load-wait 7 --capture-screenshots
```

---

### Problem: Chrome crashes in headless mode

**Solution: Try Firefox**
```bash
python main.py --project opinion_route --browser firefox --capture-screenshots
```

Or disable headless:
```bash
python main.py --project opinion_route --no-headless --capture-screenshots
```

---

## Quick Reference Cheat Sheet

```bash
# Default: captures screenshots, compares against Figma, threshold 0.90
python main.py --project opinion_route --capture-screenshots

# Strict compliance check
python main.py --project opinion_route --threshold 0.98 --max-diff-pct 0.002 --tile-threshold 0.90 --fetch-figma --capture-screenshots

# Week-to-week regression
python main.py --project opinion_route --baseline-mode screenshot --capture-screenshots

# High-DPI/Retina support
python main.py --project opinion_route --dpr 2.0 --capture-screenshots

# Debug mode (see browser, longer wait)
python main.py --project opinion_route --no-headless --page-load-wait 5 --capture-screenshots

# Firefox testing
python main.py --project opinion_route --browser firefox --capture-screenshots

# Permissive threshold (dynamic content)
python main.py --project opinion_route --threshold 0.85 --max-diff-pct 0.02 --tile-threshold 0.80 --capture-screenshots

# Localized-regression-sensitive testing
python main.py --project opinion_route --threshold 0.95 --max-diff-pct 0.002 --tile-threshold 0.90 --capture-screenshots
```

---

## Key Takeaways

1. **Use all three metrics together** — global SSIM, diff-pixel %, and worst-tile SSIM
2. **Default profile is balanced** — suitable for general visual regression detection
3. **Tighten local checks for text/icon defects** — lower `--max-diff-pct`, raise `--tile-threshold`
4. **Visual inspection remains valuable** — review tile heatmap and side-by-side panels
5. **Tune by scenario** — combine flags (for example `--dpr 2.0 --tile-threshold 0.90`)

---

**Last Updated:** June 19, 2026
