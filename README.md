# Visual Testing Framework

Python-based visual regression framework for comparing live screenshots against baselines (Figma image files or previous screenshots), then generating HTML reports.

## What It Does

- Captures live screenshots with Selenium (Chrome, Firefox, Edge)
- Compares images using three checks:
  - Global SSIM
  - Significant pixel-diff percentage
  - Worst-tile SSIM
- Generates HTML reports with copied comparison artifacts
- Supports multiple projects under `projects/`

## Important Behavior

- Baseline mode `auto` is non-interactive.
  - No previous screenshot found: uses `figma`
  - Previous screenshot found: uses `screenshot`
  - Resolved mode is written back to `testcases.yaml`
- `--fetch-figma` fetches Figma file JSON metadata only.
  - It does not download baseline PNGs.
  - Baseline image files must exist in `projects/<project>/figma_images/`.

## Project Layout

```text
VisualTesting_v1/
|- main.py
|- requirements.txt
|- core/
|  |- comparison.py
|  |- figma_client.py
|  |- reporter.py
|  |- runner.py
|  |- screenshot.py
|  \- ...
|- templates/
|  \- report.html
\- projects/
   \- <project>/
      |- testcases.yaml
      |- figma_images/
      |- screenshots/
      |- diffs/
      |- reports/
      \- logs/
```

## Setup

Prerequisites:

- Python 3.11+
- Chrome, Firefox, or Edge installed

Install:

```bash
cd VisualTesting_v1
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Testcase Configuration

Example `projects/<project>/testcases.yaml`:

```yaml
run_mode: selected
baseline_mode: auto
figma_access_token: figd_your_token_here

test_cases:
  - name: desktop_homepage
    run: true
    device: Desktop
    figma_file_name: 1440_figma.png
    url: https://example.com/
    figma_file_id: abc123def456
```

Common fields:

- `run_mode`: `all`, `selected`, or a specific test name
- `baseline_mode`: `auto`, `figma`, `screenshot`
- `figma_access_token`: optional global token (can be overridden per test)
- Per test:
  - `name`, `run`, `device`, `figma_file_name`, `url`
  - `figma_file_id` is optional and used by `--fetch-figma`

## Quick Start

```bash
# Capture new screenshots and compare
python main.py --project opinion_route --capture-screenshots
```

## CLI Arguments and Examples

This section covers all arguments currently supported by `main.py`.

Project selection:

- `--project NAME` or `-p NAME` (required)

```bash
python main.py --project opinion_route
python main.py -p opinion_route
```

Baseline behavior:

- `--baseline-mode {auto|figma|screenshot}`

```bash
python main.py --project opinion_route --baseline-mode auto
python main.py --project opinion_route --baseline-mode figma
python main.py --project opinion_route --baseline-mode screenshot
```

Comparison quality:

- `--threshold FLOAT`
- `--max-diff-pct FLOAT`
- `--diff-sensitivity INT`
- `--tile-threshold FLOAT`
- `--tile-size INT`

```bash
python main.py --project opinion_route --threshold 0.92
python main.py --project opinion_route --max-diff-pct 0.003
python main.py --project opinion_route --diff-sensitivity 25
python main.py --project opinion_route --tile-threshold 0.88
python main.py --project opinion_route --tile-size 160
```

Display normalization:

- `--dpr FLOAT`

```bash
python main.py --project opinion_route --dpr 2.0
```

Actions:

- `--capture-screenshots`
- `--fetch-figma`

```bash
python main.py --project opinion_route --capture-screenshots
python main.py --project opinion_route --fetch-figma
```

Browser and timing:

- `--browser {chrome|firefox|edge}`
- `--no-headless`
- `--page-load-timeout SECONDS`

```bash
python main.py --project opinion_route --browser firefox
python main.py --project opinion_route --no-headless
python main.py --project opinion_route --page-load-timeout 60
```

Reporting:

- `--report-name FILENAME`

```bash
python main.py --project opinion_route --report-name run_local.html
```

Combined end-to-end example:

```bash
python main.py --project opinion_route --baseline-mode screenshot --capture-screenshots --threshold 0.95 --max-diff-pct 0.002 --diff-sensitivity 25 --tile-threshold 0.90 --tile-size 180 --dpr 2.0 --browser chrome --page-load-timeout 60 --report-name strict_regression.html
```

Print built-in CLI help:

```bash
python main.py --help
```

## Output

Each run writes:

- Report directory: `projects/<project>/reports/<report_name>/`
- Main report file: `projects/<project>/reports/<report_name>/report.html`
- Copied images: `projects/<project>/reports/<report_name>/images/`
- Diff artifacts: `projects/<project>/diffs/<test_name>/`

Exit code:

- `0`: all tests passed or skipped
- `1`: any test failed or errored

## Troubleshooting

`testcases.yaml not found`

- Ensure `projects/<project>/testcases.yaml` exists.

`No screenshot available`

- Run with `--capture-screenshots` first.

`Figma image not found`

- Place the expected PNG in `projects/<project>/figma_images/`.

`Unexpected failures on high-DPI screens`

- Set DPR, for example: `--dpr 2.0`.

`Headless browser issues`

- Try `--browser firefox` or use `--no-headless`.
