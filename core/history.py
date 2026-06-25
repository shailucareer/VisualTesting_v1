"""
Generates a history index page listing all past test executions.
Allows users to navigate and view previous reports and logs.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from jinja2 import Environment, FileSystemLoader

from .logging_config import get_logger

logger = get_logger("core.history")


class HistoryGenerator:
    def __init__(self, project: str, project_path: Path, reports_dir: Path):
        self.project = project
        self.project_path = project_path
        self.reports_dir = reports_dir
        self._templates_dir = Path(__file__).parent.parent / "templates"

    def generate(self) -> str:
        """Generate history.html and return its path."""
        logger.debug(f"Generating history page for project: {self.project}")
        
        # Collect all reports with their metadata
        reports = self._collect_reports()
        logger.debug(f"Found {len(reports)} reports")
        
        # Sort by timestamp descending (newest first)
        reports.sort(key=lambda x: x['timestamp_raw'], reverse=True)
        
        # Render template
        env = Environment(loader=FileSystemLoader(self._templates_dir))
        template = env.get_template("history.html")
        
        context = {
            "project": self.project,
            "total_executions": len(reports),
            "reports": reports,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        
        html_content = template.render(context)
        
        # Write to history.html in reports directory with UTF-8 encoding
        history_path = self.reports_dir / "history.html"
        history_path.write_text(html_content, encoding="utf-8")
        logger.info(f"History page generated: {history_path}")
        
        return str(history_path)
    
    def _collect_reports(self) -> List[Dict]:
        """Collect metadata from all reports."""
        reports = []
        
        if not self.reports_dir.exists():
            logger.debug(f"Reports directory does not exist: {self.reports_dir}")
            return reports
        
        for item in self.reports_dir.iterdir():
            if item.is_dir() and item.name.startswith("report_"):
                report_data = self._extract_report_data(item)
                if report_data:
                    reports.append(report_data)
        
        return reports
    
    def _extract_report_data(self, report_dir: Path) -> Dict:
        """Extract metadata from a report directory."""
        try:
            # Extract timestamp from directory name (e.g., "report_20260619_111040")
            parts = report_dir.name.split("_")
            if len(parts) < 3:
                return None
            
            date_str = parts[1]  # e.g., "20260619"
            time_str = parts[2]  # e.g., "111040"
            
            # Parse timestamp
            timestamp_str = f"{date_str}_{time_str}"
            try:
                dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            except ValueError:
                return None
            
            # Check for report.html
            report_html = report_dir / "report.html"
            if not report_html.exists():
                return None
            
            # Try to read metadata.json first
            metadata_file = report_dir / "metadata.json"
            summary = None
            duration = None
            runtime_parameters = {}
            if metadata_file.exists():
                try:
                    with open(metadata_file, "r", encoding="utf-8") as fh:
                        metadata = json.load(fh)
                        summary = metadata.get("summary", {})
                        duration = metadata.get("duration")
                        runtime_parameters = metadata.get("runtime_parameters") or {}
                except Exception as e:
                    logger.debug(f"Failed to read metadata.json from {report_dir}: {e}")
            
            # Find logs associated with this report.
            # Logs are stored at project-level logs/ directory, not inside each report folder.
            log_files = self._find_logs_for_report(report_dir.name)
            
            # Count test results from report.html if possible (fallback)
            test_count = None
            if summary:
                test_count = summary.get("total")
            if test_count is None:
                test_count = self._count_tests(report_html)
            
            return {
                "name": report_dir.name,
                "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp_raw": dt,
                "date": dt.strftime("%b %d, %Y"),
                "time": dt.strftime("%H:%M:%S"),
                "report_path": f"{report_dir.name}/report.html",
                "logs_dir": "../logs" if log_files else None,
                "log_files": log_files,
                "test_count": test_count,
                "relative_dir": report_dir.name,
                "summary": summary if summary else {},  # Add summary stats
                "duration": duration,
                "runtime_parameters": runtime_parameters,
            }
        except Exception as e:
            logger.debug(f"Error extracting report data from {report_dir}: {e}")
            return None
    
    def _count_tests(self, report_html: Path) -> Optional[int]:
        """Attempt to count tests from report HTML."""
        try:
            content = report_html.read_text(encoding="utf-8", errors="ignore")

            # Preferred: parse the summary "Total" stat card.
            total_match = re.search(
                r'<div class="stat-num"[^>]*>\s*(\d+)\s*</div>\s*<div class="stat-lbl">\s*Total\s*</div>',
                content,
                re.IGNORECASE,
            )
            if total_match:
                return int(total_match.group(1))

            # Fallback for current card-based report format.
            card_count = len(re.findall(r'<div class="test-card"\s+data-status=', content, re.IGNORECASE))
            if card_count > 0:
                return card_count

            # Legacy fallback for table-based report format.
            row_count = content.count('<tr class="test-row')
            if row_count > 0:
                return row_count

            return None
        except Exception:
            return None

    def _find_logs_for_report(self, report_name: str) -> List[str]:
        """Return log filenames that mention the generated report path."""
        logs_dir = self.project_path / "logs"
        if not logs_dir.exists():
            return []

        matched_logs: List[str] = []
        for log_file in sorted(logs_dir.glob("*.log")):
            try:
                content = log_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            if report_name in content:
                matched_logs.append(log_file.name)

        return matched_logs
