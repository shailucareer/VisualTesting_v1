# Visual Testing Framework

A Python-based visual testing framework for comparing UI screenshots against baseline images (Figma designs or previous screenshots) with custom HTML report generation.

## Overview

This framework automates visual regression testing by:

- **Downloading Figma design images** via the REST API
- **Capturing live app screenshots** using Selenium with support for multiple browsers
- **Comparing images** using a multi-algorithm engine:
   - Global SSIM (scikit-image)
   - Significant pixel-difference ratio
   - Worst-tile SSIM (localized checks)
- **Generating rich HTML reports** with side-by-side comparisons and interactive diff sliders
- **Supporting multiple sub-projects** with per-project configuration

## Key Features

✓ **DPR Awareness** — Handle retina/HiDPI displays by scaling screenshots before comparison  
✓ **Flexible Baseline Modes** — Compare against Figma designs or previous screenshots  
✓ **Multi-Device Support** — Desktop, tablet, and mobile viewports  
✓ **External Images in Reports** — Images stored in separate `images/` folder with relative paths  
✓ **Configurable Multi-Checks** — Tune global SSIM, pixel-diff %, and tile SSIM independently  
✓ **Multi-Browser Support** — Chrome, Firefox, Edge  
✓ **Structured Logging** — Timestamps, file locations, method names, and detailed processing steps  

## Project Structure

```
VisualTesting_v1/
├── main.py                        # CLI entry point (parameterized by project)
├── requirements.txt               # Python dependencies
├── .gitignore                     # Git ignore patterns
├── .venv/                         # Local virtual environment
├── .vscode/
│   └── settings.json              # VS Code workspace settings (points to .venv)
├── core/
│   ├── figma_client.py            # Figma REST API client
│   ├── screenshot.py              # Selenium full-page capture
│   ├── comparison.py              # Multi-algorithm image comparison engine
│   ├── runner.py                  # Test orchestration
│   ├── reporter.py                # HTML report generation
│   ├── logging_config.py           # Structured logging setup
│   └── __init__.py
├── templates/
│   └── report.html                # Jinja2 HTML report template
└── projects/
    └── qcflow/                    # Example sub-project
        ├── testcases.yaml         # Test configuration
        ├── figma_images/          # Downloaded Figma PNGs
        ├── screenshots/           # Captured live screenshots
        ├── reports/               # Generated HTML reports
        └── diffs/                 # Diff images per test
```

## Installation

### Prerequisites

- Python 3.11+
- Chrome/Firefox/Edge browser for Selenium

### Setup

1. Clone or download this repository
2. Create virtual environment (already set up if using .venv):
   ```bash
   cd VisualTesting_v1
   .\.venv\Scripts\activate   # Windows
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Quick Start

### 1. Configure Test Cases

Edit `projects/<project_name>/testcases.yaml`:

```yaml
test_cases:
  - name: desktop_homepage
    run: true
    device: Desktop
    figma_file_name: 1440_figma.png
    url: https://example.com/
    figma_access_token: figd_your_token_here
    figma_file_id: abc123def456
    figma_node_id: '1202-3193'
```

**Fields:**
- `name` — Unique identifier (used in filenames & reports)
- `run` — Set to `false` to skip this test
- `device` — Viewport preset: `Desktop` (1440×900), `Desktop Large` (1920×1080), `Tablet` (768×1024), `Mobile` (375×812), `Mobile Large` (414×896)
- `figma_file_name` — Local filename for the Figma image
- `url` — Live URL to test
- `figma_access_token` — Personal Figma token (create at https://www.figma.com/developers/api#personal_access_tokens)
- `figma_file_id` — File key from Figma URL: `https://www.figma.com/file/<file_id>/...`
- `figma_node_id` — Node ID (format: `1202-3193` or `1202:3193`)

### 2. Run Tests

#### Full run (fetch Figma data + capture screenshots + compare):
```bash
python main.py --project opinion_route --fetch-figma --capture-screenshots
```

#### Compare using existing screenshots:
```bash
python main.py --project opinion_route
```

#### Use previous screenshot as baseline (regression):
```bash
python main.py --project opinion_route --baseline-mode screenshot --capture-screenshots
```

#### High-DPI / Retina displays (2× scale):
```bash
python main.py --project opinion_route --dpr 2.0 --capture-screenshots
```

#### Tighter global SSIM threshold (99% similarity):
```bash
python main.py --project qcflow --threshold 0.99
```

#### Catch local differences aggressively (missing text/icons):
```bash
python main.py --project opinion_route --capture-screenshots --max-diff-pct 0.002 --tile-threshold 0.90
```

#### Show browser window (for debugging):
```bash
python main.py --project qcflow --no-headless --capture-screenshots
```

#### Use Firefox instead of Chrome:
```bash
python main.py --project qcflow --browser firefox --capture-screenshots
```

### 3. View Reports

After a test run, open the generated HTML report:
```
projects/qcflow/reports/report_YYYYMMDD_HHMMSS/
├── report.html                  # Main HTML report
└── images/                       # Comparison images
    ├── baseline_*.png
    ├── actual_*.png
    └── diff_*.png
```

The report includes:
- Summary statistics (pass rate, counts)
- Per-test comparison panels
- Side-by-side baseline/actual/diff images
- Interactive diff slider
- Status filters (all, passed, failed, error, skipped)
- Full-size image modal viewer

**Note:** Keep the `images/` folder with `report.html` when sharing reports.

## CLI Reference

```
python main.py --help
```

### Required Arguments
- `--project NAME` — Sub-project folder name (e.g., `qcflow`)

### Optional Arguments

**Baseline Mode**
- `--baseline-mode {auto|figma|screenshot}` — Default: `auto`
   - `auto` — Use Figma on first run; if previous screenshots exist, choose baseline dynamically
   - `figma` — Compare against Figma design images
   - `screenshot` — Compare against previous captured screenshot (falls back to Figma if unavailable)

**Quality Control**
- `--threshold FLOAT` — Minimum global SSIM score (0.0–1.0). Default: `0.90`
- `--max-diff-pct FLOAT` — Max allowed % of significantly-different pixels (0.0–1.0). Default: `0.005` (0.5%)
- `--diff-sensitivity INT` — Pixel channel delta (1–255) used by `--max-diff-pct`. Default: `30`
- `--tile-threshold FLOAT` — Minimum SSIM allowed for any tile (0.0–1.0). Default: `0.85`
- `--tile-size INT` — Tile size in pixels for tiled SSIM. Default: `200`
- `--dpr FLOAT` — Device Pixel Ratio for screenshots. Default: `1.0`

**Actions**
- `--capture-screenshots` — Capture fresh screenshots via Selenium
- `--fetch-figma` — Fetch Figma JSON metadata (requires credentials in testcases.yaml)

**Browser Options**
- `--browser {chrome|firefox|edge}` — Default: `chrome`
- `--no-headless` — Show browser window (debugging mode)
- `--page-load-wait SECONDS` — Wait time after page load. Default: `3`

**Report**
- `--report-name FILENAME` — Custom report filename (auto-timestamped if omitted)

## Logging

All operations log to console with structured formatting:

```
[2026-06-19 14:32:15.123] [INFO   ] [core.runner            ] [run                ] Running test: desktop_homepage
[2026-06-19 14:32:16.456] [DEBUG  ] [core.figma_client      ] [download_image     ] Downloading Figma image from file abc123
[2026-06-19 14:32:18.789] [INFO   ] [core.screenshot        ] [capture            ] Capturing screenshot at 1440×900, DPR=1.0
[2026-06-19 14:32:22.012] [DEBUG  ] [core.comparison        ] [compare            ] SSIM score: 0.9456 (threshold: 0.9000)
[2026-06-19 14:32:22.034] [INFO   ] [core.reporter          ] [generate           ] Report generated at projects/qcflow/reports/report.html
```

**Log Format:**
`[TIMESTAMP] [LEVEL] [MODULE] [METHOD] MESSAGE`

**Log Levels:**
- `DEBUG` — Low-level details (e.g., pixel dimensions, API requests)
- `INFO` — Key milestones (e.g., test started, image saved)
- `WARNING` — Non-critical issues (e.g., missing file, fallback used)
- `ERROR` — Test failures and exceptions

Logs are written to:
- **Console** (stdout/stderr)
- **File** (optional) — `projects/<project>/logs/<date>.log`

## Image Comparison Algorithm

The framework uses a multi-algorithm fail-safe approach. A test passes only when all checks pass.

1. **DPR Normalization** — If DPR > 1, downscale screenshot by that factor
2. **Size Normalization** — Resize/crop/pad actual image to match baseline dimensions
3. **Global SSIM** — Compute full-image SSIM using scikit-image
4. **Pixel-Diff Check** — Compute % of pixels with channel diff above sensitivity threshold
5. **Worst-Tile SSIM** — Split image into tiles and fail if any tile SSIM is below threshold
6. **Diff Generation** — Create side-by-side Baseline | Actual | Tile Heatmap PNG
7. **Verdict** — Pass only if all three metric checks pass

### Metric Interpretation

- **Global SSIM**
   - `1.0` — Structurally identical
   - `0.9–0.99` — Minor differences
   - `< 0.9` — Increasingly visible structural change
- **Diff Pixels %**
   - Lower is better; default pass is `<= 0.5%`
   - Useful for catching subtle local changes not reflected in global SSIM
- **Worst-Tile SSIM**
   - Lower indicates a localized hotspot
   - Default pass requires each tile `>= 0.85`

## Figma Integration

### Getting Your Credentials

1. **Access Token** — https://www.figma.com/developers/api#personal_access_tokens
   - Click "Create a new personal access token"
   - Copy the token (starts with `figd_`)

2. **File ID** — From Figma URL: `https://www.figma.com/file/<FILE_ID>/...`

3. **Node ID** — Right-click a component in Figma → "Copy link" → extract from URL
   - Format: `1202-3193` or `1202:3193`

### Rate Limits

Figma API allows ~120 requests/min per account. Each image download = 1 request.

## Troubleshooting

### "testcases.yaml not found"
Ensure `projects/<project>/testcases.yaml` exists with proper YAML syntax.

### "No screenshots available"
Run with `--capture-screenshots` first, or manually place PNG files in `projects/<project>/screenshots/`.

### "Figma access token invalid"
Check token in testcases.yaml (should start with `figd_`). Regenerate if expired.

### "SSIM score is 0.50 but I expected higher"
- Check DPR setting (if actual page is 2× density, use `--dpr 2.0`)
- Lower threshold if acceptable differences exist: `--threshold 0.85`
- Inspect generated diff image to visually confirm differences

### Chrome crashes in headless mode
Try: `--browser firefox` or disable headless: `--no-headless`

## Development

### Adding a New Sub-Project

1. Create folder:
   ```bash
   mkdir projects/my_project
   mkdir projects/my_project/{figma_images,screenshots,reports,diffs}
   ```

2. Create `testcases.yaml`:
   ```yaml
   test_cases:
     - name: test_1
       run: true
       device: Desktop
       figma_file_name: design.png
       url: https://example.com/
       figma_access_token: figd_...
       figma_file_id: ...
       figma_node_id: ...
   ```

3. Run:
   ```bash
   python main.py --project my_project --capture-screenshots --download-figma
   ```

### Extending the Framework

Core modules are designed for extension:

- **ImageComparator** — Subclass to implement custom comparison algorithms
- **ScreenshotCapture** — Add drivers for other browsers
- **FigmaClient** — Extend for batch downloads or other API calls
- **ReportGenerator** — Customize HTML template in `templates/report.html`

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| selenium | ≥4.15 | Browser automation |
| webdriver-manager | ≥4.0 | Auto ChromeDriver/GeckoDriver |
| Pillow | ≥10.0 | Image processing |
| scikit-image | ≥0.21 | SSIM computation (fallback) |
| numpy | ≥1.24 | Numerical arrays |
| requests | ≥2.31 | HTTP client (Figma API) |
| PyYAML | ≥6.0 | YAML parsing |
| Jinja2 | ≥3.1 | HTML templating |
| watchui | ≥2.0 | Advanced image comparison |
| robotframework | ≥6.0 | (watchui dependency) |

## License

MIT License — Feel free to modify and distribute.

## Support

For issues, questions, or contributions:
1. Check the troubleshooting section above
2. Review generated log files in `projects/<project>/logs/`
3. Run with `--no-headless` to visually debug screenshot capture
4. Inspect diff images to understand comparison failures

---

**Last Updated:** June 19, 2026
