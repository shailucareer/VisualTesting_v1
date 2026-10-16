from PIL import Image

from core.comparison import ImageComparator


def compare_images(baseline, actual, output_dir):
    baseline_path = output_dir / "baseline.png"
    actual_path = output_dir / "actual.png"
    baseline.save(baseline_path)
    actual.save(actual_path)
    return ImageComparator(
        threshold=0.9,
        max_diff_pct=1.0,
        diff_sensitivity=10,
        tile_threshold=0.98,
        tile_size=50,
    ).compare(
        str(baseline_path),
        str(actual_path),
        str(output_dir / "diffs"),
    )


def test_identical_images_have_full_match_coverage(tmp_path):
    image = Image.new("RGB", (100, 100), "white")

    result = compare_images(image, image.copy(), tmp_path)

    assert result.match_coverage == 1.0


def test_completely_different_images_have_zero_match_coverage(tmp_path):
    baseline = Image.new("RGB", (100, 100), "white")
    actual = Image.new("RGB", (100, 100), "black")

    result = compare_images(baseline, actual, tmp_path)

    assert result.match_coverage == 0.0


def test_partial_match_coverage_reflects_matching_image_area(tmp_path):
    baseline = Image.new("RGB", (100, 100), "white")
    actual = Image.new("RGB", (100, 100), "white")
    for y in range(100):
        for x in range(50, 100):
            actual.putpixel((x, y), (0, 0, 0))

    result = compare_images(baseline, actual, tmp_path)

    assert result.match_coverage == 0.5
