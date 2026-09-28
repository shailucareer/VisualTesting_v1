# Visual Testing Workflow

This document describes the end-to-end workflow of the visual testing framework, including input, process, logic, and output.

## 1. Input

### 1.1 CLI Inputs

Run entry point:

```bash
python main.py --project <project_name> [options]
```

Primary CLI options:

- `--project` (required): project folder under `projects/`
- `--baseline-mode` (optional): `auto`, `figma`, or `screenshot`
- `--capture-screenshots` (optional): capture fresh live screenshots
- `--fetch-figma` (optional): fetch Figma file JSON metadata
- `--threshold` (optional): SSIM pass threshold
- `--dpr` (optional): device pixel ratio normalization factor
- `--browser`, `--no-headless`, `--page-load-timeout` (optional): capture behavior
  - `--browser` supports missing (defaults to `chrome`), single (for example `firefox`), or comma-separated multiple values (for example `edge,firefox,chrome`)
- `--report-name` (optional): custom report file name

### 1.2 Project Configuration Input

Source: `projects/<project>/testcases.csv`

Per test case:

- `name`, `run`, `device`, `figma_file_name`, `url`
- `page_data_load_wait` (optional)
- `figma_file_id` (optional, used for Figma file metadata fetch)
- `figma_node_id` (optional)

Runtime-only inputs:

- `--baseline-mode`
- `--figma-access-token`

### 1.3 File System Inputs

- Existing manual baseline images in `projects/<project>/figma_images/`
- Existing previous screenshots in `projects/<project>/screenshots/`
- Existing project folders for reports and diffs

## 2. Process

### Step 1: Startup and Validation

1. CLI arguments are parsed.
2. Project folder and `testcases.csv` are validated.
3. Runner is initialized with runtime options.

### Step 2: Configuration Loading

1. `testcases.csv` is read.
2. Rows with `run=true` are executed; rows with `run=false` remain visible as skipped.
3. `baseline_mode` is resolved from CLI input or auto-detected at runtime.
4. CLI `figma_access_token` is applied to Figma API calls when provided.

### Step 3: Baseline Resolution

1. If baseline mode is `auto`:
   - If no previous screenshot exists for runnable tests: use `figma`.
  - If previous screenshot exists: use `screenshot`.

### Step 4: Per-Test Execution

For each selected test:

1. Determine viewport size from `device`.
2. Prepare Figma baseline image:
  - If `--fetch-figma` is used and (`figma_access_token` + `figma_file_id`) are present: call Figma API and fetch file JSON metadata.
  - Baseline PNG is expected as a local file in `figma_images/`.
3. Capture live screenshot if `--capture-screenshots` is enabled.
  - Browser scrolls through page to trigger lazy-loaded content.
  - Capture viewport is expanded to target dimensions.
  - Just before saving, the framework checks if a vertical scrollbar is still present and increases viewport height until no scroll remains (best effort with retry cap).
  - Final screenshot is saved after returning to top of page.
4. Resolve comparison pair:
   - `figma` mode: baseline = Figma image, actual = latest screenshot.
   - `screenshot` mode: baseline = previous screenshot, actual = latest screenshot.
   - If previous screenshot is unavailable in screenshot mode, fallback baseline = Figma image (if present).
5. Run image comparison (SSIM + diff generation).
6. Store test result as passed, failed, skipped, or error.

### Step 5: Report Generation

1. Aggregate all test results.
2. Generate HTML report in `projects/<project>/reports/`.
3. Print summary and final pass/fail status.

## 3. Core Logics

### 3.1 Test Selection Logic

- `run=true`: execute the test case.
- `run=false`: mark the test as skipped in the report.

### 3.2 Baseline Logic

Priority order:

1. CLI `--baseline-mode` if not `auto`
2. Auto-detection behavior when CLI mode is `auto`

### 3.3 Figma Metadata Fetch Logic

Figma API is called only when all required values are present:

- global/per-test `figma_access_token`
- CLI `--figma-access-token`
- `figma_file_id`

If values are blank, API call is skipped and local baseline image is used.

### 3.4 Comparison Logic

- Screenshots are normalized using DPR.
- Baseline and actual images are resized/aligned as needed.
- SSIM score is computed and compared against threshold.
- Diff artifacts are produced for report visualization.

## 4. Logging

### 4.1 What Is Logged

- Run initialization and configuration
- Baseline mode resolution (`baseline_mode`)
- Test start/skip/failure/pass events
- Figma API download attempts or skip reasons
- Screenshot capture actions
  - viewport size selection and vertical-scroll pre-capture checks
- SSIM scores and comparison outcomes
- Report generation path

### 4.2 Log Levels

- `DEBUG`: internal details (paths, resolution choices, calculations)
- `INFO`: lifecycle milestones (test start/end, report generated)
- `WARNING`: recoverable issues (fallback conditions, missing optional values)
- `ERROR`: unrecoverable failures per test or run

## 5. Output

### 5.1 Primary Outputs

- HTML report: `projects/<project>/reports/<report_name>/report.html`
- Diff images: `projects/<project>/diffs/<test_name>/`
- Captured screenshots: `projects/<project>/screenshots/`
- Manual Figma images: `projects/<project>/figma_images/`

### 5.2 Runtime Output

- Console logs and test status lines
- Final summary with pass/fail/skip/error counts
- Process exit code:
  - `0` when all tests are passed or skipped
  - `1` when any test fails or errors

## 6. Quick Decision Table

| Situation | Behavior |
|---|---|
| First run, no screenshots | Use Figma baseline |
| Subsequent run, `baseline_mode=auto` | Use previous screenshot, then persist choice |
| `figma_file_id` missing | Skip Figma API call |
| Manual Figma file exists | Use manual file for comparison |
| Screenshot baseline unavailable | Fallback to Figma baseline if available |
| `testcases.csv` missing required columns | Stop with validation error |
