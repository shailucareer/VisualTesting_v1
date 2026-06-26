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

Source: `projects/<project>/testcases.yaml`

Top-level keys:

- `run_mode`: test execution selection mode
  - `all`: execute every listed test case
  - `selected`: execute only test cases with `run: true`
  - `<test_name>`: execute one specific test by name
- `baseline_mode`:
  - `auto`: first-run uses Figma; later runs use previous screenshot when available, then persist selection
  - `figma`: always compare against Figma image
  - `screenshot`: compare against previous execution screenshot
- `figma_access_token`: global token used for Figma API calls

Per test case:

- `name`, `run`, `device`, `figma_file_name`, `url`
- `figma_file_id` (optional, used for Figma file metadata fetch)

### 1.3 File System Inputs

- Existing manual baseline images in `projects/<project>/figma_images/`
- Existing previous screenshots in `projects/<project>/screenshots/`
- Existing project folders for reports and diffs

## 2. Process

### Step 1: Startup and Validation

1. CLI arguments are parsed.
2. Project folder and `testcases.yaml` are validated.
3. Runner is initialized with runtime options.

### Step 2: Configuration Loading

1. `testcases.yaml` is read.
2. `run_mode` is resolved into an executable test list.
3. `baseline_mode` is resolved (CLI override or YAML-driven behavior).
4. Global `figma_access_token` is applied to test cases by default.

### Step 3: Baseline Resolution

1. If baseline mode is `auto`:
   - If no previous screenshot exists for runnable tests: use `figma`.
  - If previous screenshot exists: use `screenshot`.
2. Resolved baseline mode is persisted back into `testcases.yaml`.

### Step 4: Per-Test Execution

For each selected test:

1. Determine viewport size from `device`.
2. Prepare Figma baseline image:
  - If `--fetch-figma` is used and (`figma_access_token` + `figma_file_id`) are present: call Figma API and fetch file JSON metadata.
  - Baseline PNG is expected as a local file in `figma_images/`.
3. Capture live screenshot if `--capture-screenshots` is enabled.
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

- `run_mode=all`: ignore per-test `run` flag and execute all listed tests.
- `run_mode=selected`: execute only `run: true`; mark others as skipped.
- `run_mode=<test_name>`: execute only the matching test; error if not found.

### 3.2 Baseline Logic

Priority order:

1. CLI `--baseline-mode` if not `auto`
2. YAML `baseline_mode` if it is `figma` or `screenshot`
3. Auto-detection behavior when YAML is `auto`

### 3.3 Figma Metadata Fetch Logic

Figma API is called only when all required values are present:

- global/per-test `figma_access_token`
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
- Mode resolution (`run_mode`, `baseline_mode`)
- Test start/skip/failure/pass events
- Figma API download attempts or skip reasons
- Screenshot capture actions
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
| Named test in `run_mode` not found | Stop with validation error |
