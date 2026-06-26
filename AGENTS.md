# AGENTS.md

Purpose: fast, low-token orientation for AI agents working in this repo.

## 1) Project in 30 Seconds
- Type: Python visual regression testing framework.
- Entry point: `main.py`.
- Core flow: load `projects/<name>/testcases.yaml` -> optionally capture screenshot -> compare against baseline (Figma image or previous screenshot) -> generate HTML report.
- Comparison signals: global SSIM, significant pixel-diff %, worst-tile SSIM.

## 2) High-Value Files Only
- `main.py`: CLI parsing and run trigger.
- `core/runner.py`: orchestration for test execution.
- `core/comparison.py`: image comparison logic and thresholds.
- `core/screenshot.py`: Selenium screenshot capture.
- `core/reporter.py`: HTML report generation.
- `core/figma_client.py`: Figma metadata fetch behavior.
- `core/history.py`: report history handling.
- `templates/report.html`, `templates/history.html`: report templates.
- `projects/<project>/testcases.yaml`: runtime config per project.

## 3) Folder Contract
- `projects/<project>/figma_images/`: baseline PNGs (must exist locally).
- `projects/<project>/screenshots/`: captured live screenshots.
- `projects/<project>/diffs/`: diff artifacts per test.
- `projects/<project>/reports/`: generated report folders and history.
- `projects/<project>/logs/`: logs.

## 4) Commands Agents Should Use
- Setup:
  - `pip install -r requirements.txt`
- Run visual test:
  - `python main.py --project <project_name> --capture-screenshots`
- Help:
  - `python main.py --help`

## 5) Baseline Behavior (Important)
- `baseline_mode=auto` is non-interactive:
  - no previous screenshot -> uses `figma`
  - previous screenshot exists -> uses `screenshot`
- Resolved mode is written back to `testcases.yaml`.
- `--fetch-figma` fetches Figma file JSON metadata only, not baseline PNG downloads.

## 6) Token-Efficient Working Rules
- Read these first: `README.md`, `WORKFLOW.md`, and target project `testcases.yaml`.
- Prefer opening only `core/*.py` needed for the specific task.
- Do not scan generated artifact trees unless debugging report output:
  - `projects/*/reports/**`
  - `projects/*/diffs/**`
  - `projects/*/screenshots/**`
  - `projects/*/logs/**`
- Avoid reading old report folders; they are large and low-signal.

## 7) Safe Defaults for Agent Changes
- Preserve CLI flags and existing YAML keys.
- Keep behavior backward-compatible unless user asks for a breaking change.
- Validate by running one focused command on the target project.
- Prefer minimal diffs in `core/` and avoid touching generated report artifacts.

## 8) Quick Troubleshooting Map
- Missing `testcases.yaml` -> check `projects/<project>/testcases.yaml` path.
- "No screenshot available" -> run with `--capture-screenshots`.
- "Figma image not found" -> ensure PNG exists in `figma_images/`.
- High-DPI mismatch -> set `--dpr` (example: `2.0`).
- Browser capture issues -> try `--browser firefox`, `--browser edge,firefox,chrome`, or `--no-headless`.

## 9) Minimal Context Prompt for Sub-Agents
Use this when spawning sub-agents:
"Python visual testing repo. Start with `main.py` and `core/runner.py`. Config is `projects/<project>/testcases.yaml`. Ignore `projects/*/reports`, `diffs`, `screenshots`, `logs` unless explicitly needed. Keep changes backward-compatible and minimal."
