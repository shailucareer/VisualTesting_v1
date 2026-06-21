# SSIM, Pixel-Diff, and Tile Threshold Guide

This reference explains how the framework decides PASS/FAIL and how to tune thresholds without overfitting.

## Pass/Fail Rule

A test passes only if all checks pass:

```text
global_ssim      >= threshold
diff_pixels_pct  <= max_diff_pct
worst_tile_ssim  >= tile_threshold
```

Defaults:

- `--threshold 0.90`
- `--max-diff-pct 0.005` (0.5%)
- `--diff-sensitivity 30`
- `--tile-threshold 0.85`
- `--tile-size 200`

## What Each Metric Catches

Global SSIM:

- Strong at broad layout and structure changes
- Can miss tiny but important local defects

Pixel-diff percentage:

- Catches subtle text/color/content shifts
- Controlled by `--max-diff-pct`
- Sensitivity controlled by `--diff-sensitivity`

Worst-tile SSIM:

- Catches localized regressions that global averages hide
- Controlled by `--tile-threshold` and `--tile-size`

## Why SSIM Alone Is Not Enough

Example:

```text
Global SSIM       = 0.97  (passes 0.90)
Diff pixels       = 0.9%  (fails 0.5%)
Worst tile SSIM   = 0.72  (fails 0.85)
Final verdict     = FAIL
```

This behavior is intentional and useful for small but important UI regressions.

## Tuning Profiles

Permissive:

```bash
python main.py --project opinion_route --capture-screenshots --threshold 0.85 --max-diff-pct 0.02 --tile-threshold 0.80
```

Balanced (default-like):

```bash
python main.py --project opinion_route --capture-screenshots
```

Strict:

```bash
python main.py --project opinion_route --capture-screenshots --threshold 0.95 --max-diff-pct 0.002 --tile-threshold 0.90
```

High-DPI systems:

```bash
python main.py --project opinion_route --capture-screenshots --dpr 2.0
```

## Practical Troubleshooting

Test passes but visible difference exists:

- Raise `--threshold`
- Lower `--max-diff-pct`
- Raise `--tile-threshold`
- Lower `--tile-size` for tighter localization

Test fails but change looks acceptable:

- Lower `--threshold`
- Raise `--max-diff-pct`
- Lower `--tile-threshold`
- Verify DPR and browser consistency

Page captured too early:

- Increase `--page-load-wait`

Browser instability in headless mode:

- Try `--browser firefox` or run with `--no-headless`

## Notes

- `--fetch-figma` fetches Figma file JSON metadata only.
- Baseline PNG files are still expected in `figma_images/`.

Last updated: June 20, 2026
