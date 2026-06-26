"""
Generates custom HTML reports from test results.
Images are stored in a separate 'images' subfolder with relative paths.
Logs report generation progress and file paths.
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from jinja2 import Environment, FileSystemLoader

from .logging_config import get_logger
from .history import HistoryGenerator

logger = get_logger("core.reporter")


class ReportGenerator:
    def __init__(self, project: str, project_path: Path, reports_dir: Path):
        self.project = project
        self.project_path = project_path
        self.reports_dir = reports_dir
        self._templates_dir = Path(__file__).parent.parent / "templates"

    def generate(self, results, report_name: Optional[str] = None, runtime_metadata: Optional[dict] = None) -> str:
        """Render the HTML report and return its absolute path."""
        logger.debug(f"Starting HTML report generation for project: {self.project}")
        ts = datetime.now()

        if not report_name:
            report_name = f"report_{ts.strftime('%Y%m%d_%H%M%S')}"
        if report_name.endswith(".html"):
            report_name = report_name[:-5]

        # Create report directory with images subfolder
        report_dir = self.reports_dir / report_name
        report_dir.mkdir(parents=True, exist_ok=True)
        images_dir = report_dir / "images"
        images_dir.mkdir(exist_ok=True)

        report_path = str((report_dir / "report.html").resolve())
        logger.debug(f"Report will be saved to: {report_path}")

        # ── Build per-test context dicts ──────────────────────────────
        logger.debug(f"Processing {len(results)} test results for report")
        tests_ctx = []
        for result in results:
            test_name = result.test_case.name
            if getattr(result, "browser", None):
                test_name = f"{test_name} [{result.browser}]"

            item: dict = {
                "name":          test_name,
                "run":           result.test_case.run,
                "device":        result.test_case.device,
                "url":           result.test_case.url,
                "figma_file_name": result.test_case.figma_file_name,
                "page_data_load_wait": result.test_case.page_data_load_wait,
                "status":        result.status,
                "error_message": result.error_message,
                "similarity_pct":    None,
                "threshold_pct":     None,
                "diff_pixels_pct":   None,
                "max_diff_pct":      None,
                               "worst_tile_ssim_pct": None,
                               "tile_threshold_pct":  None,
                               "failed_tiles":        None,
                               "total_tiles":         None,
                "baseline_size":     None,
                "raw_actual_size":   None,
                "normalized_baseline_size": None,
                "normalized_actual_size":   None,
                "normalization_summary":    None,
                "dpr_adjusted":      False,
                "baseline_path":     None,
                "actual_path":       None,
                "diff_path":         None,
            }

            if result.comparison:
                cmp = result.comparison
                item["similarity_pct"]  = round(cmp.similarity * 100, 2)
                item["threshold_pct"]   = round(cmp.threshold  * 100, 2)
                item["diff_pixels_pct"] = round(cmp.diff_pixels_pct * 100, 3)
                item["max_diff_pct"]    = (
                    round(cmp.max_diff_pct * 100, 3)
                    if cmp.max_diff_pct is not None else None
                )
                item["worst_tile_ssim_pct"] = round(cmp.worst_tile_ssim * 100, 2)
                item["tile_threshold_pct"]  = round(cmp.tile_threshold  * 100, 2)
                item["failed_tiles"]        = cmp.failed_tiles
                item["total_tiles"]         = cmp.total_tiles
                item["baseline_size"]   = f"{cmp.baseline_size[0]}×{cmp.baseline_size[1]}"
                item["raw_actual_size"] = f"{cmp.raw_actual_size[0]}×{cmp.raw_actual_size[1]}"
                item["normalized_baseline_size"] = (
                    f"{cmp.normalized_baseline_size[0]}×{cmp.normalized_baseline_size[1]}"
                )
                item["normalized_actual_size"] = (
                    f"{cmp.normalized_actual_size[0]}×{cmp.normalized_actual_size[1]}"
                )
                item["normalization_summary"] = cmp.normalization_summary
                item["dpr_adjusted"]    = cmp.dpr_adjusted

                # Copy images to images folder and store relative paths
                item["baseline_path"] = self._copy_image(cmp.baseline_path, images_dir, "baseline")
                item["actual_path"]   = self._copy_image(cmp.actual_path, images_dir, "actual")
                item["diff_path"]     = self._copy_image(cmp.diff_image_path, images_dir, "diff")

            tests_ctx.append(item)

        # ── Summary stats ─────────────────────────────────────────────
        total   = len(results)
        passed  = sum(1 for r in results if r.status == "passed")
        failed  = sum(1 for r in results if r.status == "failed")
        skipped = sum(1 for r in results if r.status == "skipped")
        errors  = sum(1 for r in results if r.status == "error")
        runnable = total - skipped
        pass_rate = round((passed / runnable * 100) if runnable else 0, 1)

        summary = {
            "total":     total,
            "passed":    passed,
            "failed":    failed,
            "skipped":   skipped,
            "errors":    errors,
            "pass_rate": pass_rate,
        }

        # ── Render ────────────────────────────────────────────────────
        env = Environment(loader=FileSystemLoader(str(self._templates_dir)), autoescape=True)
        template = env.get_template("report.html")
        html = template.render(
            project=self.project,
            generated_at=ts.strftime("%Y-%m-%d %H:%M:%S"),
            summary=summary,
            duration=(runtime_metadata or {}).get("duration"),
            runtime_parameters=(runtime_metadata or {}).get("runtime_parameters", {}),
            tests=tests_ctx,
        )

        with open(report_path, "w", encoding="utf-8") as fh:
            fh.write(html)
        logger.info(f"HTML report generated: {report_path} ({len(html)} bytes, images in ./images/)")

        # Save metadata.json alongside report.html
        metadata = {
            "timestamp": ts.isoformat(),
            "generated_at": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "project": self.project,
            "summary": summary,
            "duration": (runtime_metadata or {}).get("duration"),
            "duration_seconds": (runtime_metadata or {}).get("duration_seconds"),
            "runtime_parameters": (runtime_metadata or {}).get("runtime_parameters", {}),
        }
        metadata_path = str(report_dir / "metadata.json")
        with open(metadata_path, "w", encoding="utf-8") as fh:
            json.dump(metadata, fh, indent=2)
        logger.debug(f"Metadata saved: {metadata_path}")

        # Generate history index
        try:
            history_gen = HistoryGenerator(self.project, self.project_path, self.reports_dir)
            history_path = history_gen.generate()
            logger.debug(f"History page updated: {history_path}")
        except Exception as e:
            logger.warning(f"Failed to generate history page: {e}")

        return report_path

    # ------------------------------------------------------------------
    @staticmethod
    def _copy_image(src_path: Optional[str], dest_dir: Path, img_type: str) -> Optional[str]:
        """Copy image to report images folder and return relative path."""
        if not src_path or not os.path.exists(src_path):
            return None
        
        src = Path(src_path)
        filename = f"{img_type}_{src.name}"
        dest = dest_dir / filename
        
        shutil.copy2(src, dest)
        
        # Return relative path from report.html
        return f"images/{filename}"
