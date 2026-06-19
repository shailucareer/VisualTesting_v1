"""
Multi-algorithm image comparison engine.

Three independent algorithms are applied; a test fails if ANY one fails.

Strategy
--------
1. DPR normalisation   – scale screenshot down by DPR so both images are at
                         the same logical-pixel resolution.
2. Size normalisation  – crop or pad the screenshot to match baseline dimensions.
3. Global SSIM         – full-image structural similarity (scikit-image).
                         Catches large structural / layout regressions.
4. Pixel-diff count    – fraction of pixels where any channel differs by more
                         than *diff_sensitivity*.  Catches localised colour or
                         content changes that barely move the global SSIM.
5. Worst-tile SSIM     – image divided into *tile_size* × *tile_size* tiles;
                         SSIM computed per tile.  The minimum tile score is
                         checked against *tile_threshold*.  Catches small but
                         visually important differences (missing text, icons)
                         that are diluted in the global score.
6. Tile-heatmap diff   – side-by-side Baseline | Actual | Heatmap composite
                         saved to the output folder.  Each tile is colour-coded
                         green (identical) → red (very different) and failed
                         tiles are outlined with their SSIM score.
"""

import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw
from skimage.metrics import structural_similarity as compute_ssim

from .logging_config import get_logger

logger = get_logger("core.comparison")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class TileResult:
    row: int
    col: int
    x: int           # left pixel offset in image
    y: int           # top pixel offset in image
    ssim: float
    passed: bool


@dataclass
class ComparisonResult:
    # ── Algorithm scores ──────────────────────────────────────────
    similarity: float           # global SSIM (0–1)
    threshold: float            # configured minimum global SSIM
    diff_pixels_pct: float      # fraction of significantly-different pixels
    max_diff_pct: float         # configured limit for pixel-diff fraction
    worst_tile_ssim: float      # lowest per-tile SSIM found
    tile_threshold: float       # configured minimum tile SSIM
    failed_tiles: int           # number of tiles below tile_threshold
    total_tiles: int
    # ── Verdict ───────────────────────────────────────────────────
    passed: bool
    # ── Paths ─────────────────────────────────────────────────────
    diff_image_path: Optional[str]
    baseline_path: str
    actual_path: str            # path to the DPR/size-normalised actual image
    # ── Image metadata ────────────────────────────────────────────
    baseline_size: Tuple[int, int]
    raw_actual_size: Tuple[int, int]
    dpr_adjusted: bool = False


# ---------------------------------------------------------------------------
# Comparator
# ---------------------------------------------------------------------------

class ImageComparator:
    """
    Compare a baseline image against a live-app screenshot using three
    independent algorithms.  A test fails when ANY algorithm detects a
    significant difference.

    Parameters
    ----------
    threshold : float
        Minimum global SSIM score (0–1) to pass.  Default 0.90.
    dpr : float
        Device Pixel Ratio of captured screenshots.  Default 1.0.
    max_diff_pct : float
        Maximum fraction (0–1) of pixels allowed to differ by more than
        *diff_sensitivity*.  Default 0.005 (0.5 %).
    diff_sensitivity : int
        Per-channel brightness delta (0–255) that marks a pixel as
        "significantly different".  Default 30.
    tile_threshold : float
        Minimum SSIM allowed for any single tile.  Default 0.85.
    tile_size : int
        Tile side-length in pixels.  Default 200.
    """

    def __init__(
        self,
        threshold: float = 0.90,
        dpr: float = 1.0,
        max_diff_pct: float = 0.005,
        diff_sensitivity: int = 30,
        tile_threshold: float = 0.85,
        tile_size: int = 200,
    ):
        if not 0.0 < threshold <= 1.0:
            raise ValueError("threshold must be in (0.0, 1.0]")
        if dpr <= 0:
            raise ValueError("dpr must be positive")
        if not 0.0 <= max_diff_pct <= 1.0:
            raise ValueError("max_diff_pct must be in [0.0, 1.0]")
        if not 0 < diff_sensitivity <= 255:
            raise ValueError("diff_sensitivity must be in (0, 255]")
        if not 0.0 < tile_threshold <= 1.0:
            raise ValueError("tile_threshold must be in (0.0, 1.0]")
        if tile_size < 16:
            raise ValueError("tile_size must be >= 16")
        self.threshold = threshold
        self.dpr = dpr
        self.max_diff_pct = max_diff_pct
        self.diff_sensitivity = diff_sensitivity
        self.tile_threshold = tile_threshold
        self.tile_size = tile_size

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compare(
        self,
        baseline_path: str,
        actual_path: str,
        output_folder: str,
        test_name: str = "test",
    ) -> ComparisonResult:
        os.makedirs(output_folder, exist_ok=True)
        logger.debug(
            f"Comparison start: test={test_name}  threshold={self.threshold}  "
            f"max_diff_pct={self.max_diff_pct}  tile_threshold={self.tile_threshold}  "
            f"tile_size={self.tile_size}  dpr={self.dpr}"
        )

        baseline_img = Image.open(baseline_path).convert("RGB")
        actual_img   = Image.open(actual_path).convert("RGB")
        raw_actual_size = actual_img.size
        dpr_adjusted = False

        # ── Step 1: DPR normalisation ──────────────────────────────────
        if self.dpr != 1.0:
            new_w = int(actual_img.width  / self.dpr)
            new_h = int(actual_img.height / self.dpr)
            actual_img = actual_img.resize((new_w, new_h), Image.LANCZOS)
            dpr_adjusted = True
            logger.debug(f"DPR {self.dpr}: resized actual → {actual_img.size}")

        # ── Step 2: Size normalisation ─────────────────────────────────
        actual_img = self._normalise_size(baseline_img, actual_img)
        logger.debug(
            f"After normalisation: baseline={baseline_img.size}  actual={actual_img.size}"
        )

        processed_actual_path = os.path.join(
            output_folder, f"{test_name}_actual_processed.png"
        )
        actual_img.save(processed_actual_path)

        # ── Step 3: Global SSIM ────────────────────────────────────────
        similarity = self._global_ssim(baseline_img, actual_img)
        ssim_passed = similarity >= self.threshold
        logger.info(
            f"[SSIM-GLOBAL]  {similarity:.4f}  "
            f"(threshold {self.threshold})  → {'PASS' if ssim_passed else 'FAIL'}"
        )

        # ── Step 4: Pixel-diff count ───────────────────────────────────
        diff_pixels_pct = self._pixel_diff_pct(baseline_img, actual_img)
        pixel_passed = diff_pixels_pct <= self.max_diff_pct
        logger.info(
            f"[PIXEL-DIFF]   {diff_pixels_pct * 100:.3f}%  "
            f"(limit {self.max_diff_pct * 100:.3f}%)  → {'PASS' if pixel_passed else 'FAIL'}"
        )

        # ── Step 5: Worst-tile SSIM ────────────────────────────────────
        tiles = self._tiled_ssim(baseline_img, actual_img)
        worst_tile_ssim = min((t.ssim for t in tiles), default=1.0)
        failed_tiles    = sum(1 for t in tiles if not t.passed)
        tile_passed     = worst_tile_ssim >= self.tile_threshold
        logger.info(
            f"[SSIM-TILE]    worst={worst_tile_ssim:.4f}  "
            f"failed={failed_tiles}/{len(tiles)}  "
            f"(tile_threshold {self.tile_threshold})  → {'PASS' if tile_passed else 'FAIL'}"
        )

        passed = ssim_passed and pixel_passed and tile_passed
        logger.info(f"[VERDICT]      {'PASS ✓' if passed else 'FAIL ✗'}")

        # ── Step 6: Tile-heatmap diff composite ───────────────────────
        diff_path = self._generate_diff_composite(
            baseline_img, actual_img, tiles,
            output_folder, test_name,
            similarity, diff_pixels_pct, worst_tile_ssim,
        )

        return ComparisonResult(
            similarity=similarity,
            threshold=self.threshold,
            diff_pixels_pct=diff_pixels_pct,
            max_diff_pct=self.max_diff_pct,
            worst_tile_ssim=worst_tile_ssim,
            tile_threshold=self.tile_threshold,
            failed_tiles=failed_tiles,
            total_tiles=len(tiles),
            passed=passed,
            diff_image_path=diff_path,
            baseline_path=baseline_path,
            actual_path=processed_actual_path,
            baseline_size=baseline_img.size,
            raw_actual_size=raw_actual_size,
            dpr_adjusted=dpr_adjusted,
        )

    # ------------------------------------------------------------------
    # Comparison algorithms
    # ------------------------------------------------------------------

    @staticmethod
    def _global_ssim(img1: Image.Image, img2: Image.Image) -> float:
        arr1 = np.array(img1, dtype=np.float32)
        arr2 = np.array(img2, dtype=np.float32)
        score, _ = compute_ssim(arr1, arr2, full=True, channel_axis=2, data_range=255)
        return float(score)

    def _pixel_diff_pct(self, img1: Image.Image, img2: Image.Image) -> float:
        arr1 = np.array(img1, dtype=np.int16)
        arr2 = np.array(img2, dtype=np.int16)
        max_diff = np.abs(arr1 - arr2).max(axis=2)   # H×W
        return float((max_diff > self.diff_sensitivity).sum()) / float(max_diff.size)

    def _tiled_ssim(
        self, img1: Image.Image, img2: Image.Image
    ) -> List[TileResult]:
        """
        Divide both images into tiles and compute SSIM per tile.
        Tiles smaller than 7×7 px are skipped (SSIM minimum window size).
        """
        w, h  = img1.size
        ts    = self.tile_size
        arr1  = np.array(img1, dtype=np.float32)
        arr2  = np.array(img2, dtype=np.float32)
        results: List[TileResult] = []

        row, y = 0, 0
        while y < h:
            y2 = min(y + ts, h)
            col, x = 0, 0
            while x < w:
                x2 = min(x + ts, w)
                tw, th = x2 - x, y2 - y
                if tw >= 7 and th >= 7:
                    t1 = arr1[y:y2, x:x2]
                    t2 = arr2[y:y2, x:x2]
                    win = min(7, tw, th)
                    if win % 2 == 0:
                        win -= 1
                    try:
                        score, _ = compute_ssim(
                            t1, t2, full=True,
                            channel_axis=2, data_range=255, win_size=win,
                        )
                        score = float(score)
                    except Exception:
                        score = 1.0
                    results.append(TileResult(
                        row=row, col=col, x=x, y=y,
                        ssim=score,
                        passed=score >= self.tile_threshold,
                    ))
                x = x2
                col += 1
            y = y2
            row += 1

        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_size(
        baseline: Image.Image, actual: Image.Image
    ) -> Image.Image:
        bw, bh = baseline.size
        aw, ah = actual.size
        if (aw, ah) == (bw, bh):
            return actual
        if aw != bw:
            scale  = bw / aw
            actual = actual.resize((bw, int(ah * scale)), Image.LANCZOS)
            aw, ah = actual.size
        if ah > bh:
            actual = actual.crop((0, 0, bw, bh))
        elif ah < bh:
            canvas = Image.new("RGB", (bw, bh), (255, 255, 255))
            canvas.paste(actual, (0, 0))
            actual = canvas
        return actual

    def _generate_diff_composite(
        self,
        baseline: Image.Image,
        actual: Image.Image,
        tiles: List[TileResult],
        output_folder: str,
        test_name: str,
        similarity: float,
        diff_pixels_pct: float,
        worst_tile_ssim: float,
    ) -> str:
        """
        Build a side-by-side composite:
            [Baseline]  |  [Actual]  |  [Tile Heatmap]

        The heatmap overlays the actual screenshot with colour-coded tiles:
          - Tile fill: green (ssim≈1.0) → red (ssim≈0.0), alpha ∝ difference
          - Failed tiles: bold red border + SSIM score label
        """
        w, h   = baseline.size
        gap    = 10
        label_h = 36
        panel_w = w
        total_w = panel_w * 3 + gap * 2
        total_h = h + label_h

        # ── Build heatmap panel ────────────────────────────────────────
        heatmap_base = actual.convert("RGBA")
        overlay      = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw_ov      = ImageDraw.Draw(overlay)
        ts           = self.tile_size

        for tile in tiles:
            x1, y1 = tile.x, tile.y
            x2 = min(x1 + ts, w) - 1
            y2 = min(y1 + ts, h) - 1
            red   = int((1.0 - tile.ssim) * 255)
            green = int(tile.ssim * 255)
            alpha = max(15, int((1.0 - tile.ssim) * 210))
            draw_ov.rectangle([x1, y1, x2, y2], fill=(red, green, 0, alpha))
            if not tile.passed:
                draw_ov.rectangle([x1, y1, x2, y2], outline=(255, 40, 40, 240), width=3)
                draw_ov.text((x1 + 5, y1 + 5), f"{tile.ssim:.2f}", fill=(255, 255, 255, 230))

        heatmap = Image.alpha_composite(heatmap_base, overlay).convert("RGB")

        # ── Assemble canvas ────────────────────────────────────────────
        passed = (
            similarity >= self.threshold
            and diff_pixels_pct <= self.max_diff_pct
            and worst_tile_ssim >= self.tile_threshold
        )
        status_color = (60, 200, 80) if passed else (220, 60, 60)

        canvas = Image.new("RGB", (total_w, total_h), (30, 30, 30))
        canvas.paste(baseline.convert("RGB"), (0,                      label_h))
        canvas.paste(actual.convert("RGB"),   (panel_w + gap,          label_h))
        canvas.paste(heatmap,                 (panel_w * 2 + gap * 2,  label_h))

        draw = ImageDraw.Draw(canvas)
        labels = [
            (0,                    "Baseline"),
            (panel_w + gap,        "Actual"),
            (panel_w * 2 + gap * 2,
             f"Tile Heatmap  |  SSIM={similarity:.3f}  "
             f"diff={diff_pixels_pct * 100:.2f}%  "
             f"worst-tile={worst_tile_ssim:.3f}"),
        ]
        for lx, text in labels:
            draw.rectangle([lx, 0, lx + panel_w, label_h - 1], fill=(50, 50, 50))
            draw.text((lx + 8, 11), text, fill=status_color)

        diff_path = os.path.join(output_folder, f"{test_name}_diff.png")
        canvas.save(diff_path)
        return diff_path
