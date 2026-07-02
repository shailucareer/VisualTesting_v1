# Team Setup and Run Guide

This guide explains how a new teammate can install the visual testing project on their own machine and run it step by step.

The project is a Python-based visual regression tool that captures screenshots, compares them with a baseline image, and generates an HTML report.

## 1. Prerequisites

Before starting, make sure you have:

- Windows 10/11 (the examples below use PowerShell)
- Python 3.11 or newer
- Git
- One browser installed: Chrome, Firefox, or Edge
- Internet access for the target website and any Figma access if needed

If Python is not installed yet:

1. Download Python from https://www.python.org/downloads/
2. Install it and make sure to check the option: Add Python to PATH
3. Restart the terminal after installation

## 2. Clone the Project

Open PowerShell and run:

```powershell
git clone <your-repo-url>
cd VisualTesting_v1
```

If you already have the folder, go to it:

```powershell
cd D:\AI\VisualTesting_v1
```

## 3. Create a Virtual Environment

It is recommended to use a virtual environment so dependencies do not affect your global Python install.

```powershell
py -3.11 -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks the script, run this once:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then activate again.

## 4. Install Dependencies

Run:

```powershell
pip install -r requirements.txt
```

This installs Selenium, Pillow, scikit-image, requests, PyYAML, Jinja2, and other required packages.

## 5. Verify the Project Structure

Inside the repository, you should see folders like:

- main.py
- core/
- projects/
- templates/

Each project has its own config file under:

```text
projects/<project-name>/testcases.yaml
```

For example:

```text
projects/saudiCeramic/testcases.yaml
```

## 6. Configure the Project

Open the relevant test config file and review the values.

Example:

```powershell
notepad .\projects\saudiCeramic\testcases.yaml
```

Important fields:

- run_mode: choose all, selected, or a specific test name
- baseline_mode: auto, figma, or screenshot
- figma_access_token: optional if you use Figma
- test_cases: list of web pages to test

A simple example:

```yaml
run_mode: 'selected'
baseline_mode: 'figma'
figma_access_token:
```

If you want to run a test that uses a Figma baseline, make sure the expected image file exists in:

```text
projects/<project-name>/figma_images/
```

## 7. Run the Visual Test

### Basic run

```powershell
python main.py --project saudiCeramic
```

### Capture fresh screenshots and compare them

```powershell
python main.py --project saudiCeramic --capture-screenshots
```

### Run locally with visible browser window

```powershell
python main.py --project saudiCeramic --capture-screenshots --no-headless
```

### Use a custom tile size for better sensitivity

```powershell
python main.py --project saudiCeramic --capture-screenshots --tile-size 50 --no-headless
```

## 8. What the Run Produces

After a successful run, the project creates output in these folders:

- reports: projects/<project>/reports/
- screenshots: projects/<project>/screenshots/
- diffs: projects/<project>/diffs/
- logs: projects/<project>/logs/

You can open the generated HTML report from the report folder.

## 9. Common Troubleshooting

### Python command is not recognized

Try:

```powershell
py -3.11 --version
```

Or use the virtual environment Python directly:

```powershell
.\.venv\Scripts\python.exe --version
```

### Browser issues

If Selenium cannot start the browser:

- make sure Chrome, Edge, or Firefox is installed
- try another browser
- use the visible mode flag:

```powershell
python main.py --project saudiCeramic --capture-screenshots --no-headless
```

### No screenshot available

If the tool says no screenshot is available, run with:

```powershell
python main.py --project saudiCeramic --capture-screenshots
```

### Figma image missing

If your baseline uses a Figma image, make sure the PNG exists in:

```text
projects/saudiCeramic/figma_images/
```

### Permission issue while activating venv

Run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## 10. Useful Commands

Show help:

```powershell
python main.py --help
```

Run a specific test mode:

```powershell
python main.py --project saudiCeramic --baseline-mode figma
```

Run with a custom report name:

```powershell
python main.py --project saudiCeramic --capture-screenshots --report-name local_run.html
```

## 11. Recommended Team Workflow

1. Pull the latest code
2. Activate the virtual environment
3. Install dependencies if needed
4. Open the project config file
5. Run the test for the target project
6. Review the generated HTML report and image diffs

If you want, this guide can also be expanded into a shorter "quick start" version for new team members.
