from core.screenshot import ScreenshotCapture


class CaptureDriver:
    def __init__(self):
        self.width = 0
        self.height = 0
        self.window_sizes = []

    def set_page_load_timeout(self, _timeout):
        pass

    def get(self, _url):
        pass

    def execute_script(self, script, *_args):
        if "return document.body.scrollHeight" in script:
            return 804
        if "viewportHeight" in script and "body.scrollHeight" in script:
            return 804
        if "window.innerWidth" in script and "window.innerHeight" in script:
            return {"width": self.width, "height": self.height}
        if "window.scrollTo" in script:
            return None
        raise AssertionError(f"Unexpected script: {script}")

    def set_window_size(self, width, height):
        self.width = width
        self.height = height
        self.window_sizes.append((width, height))

    def get_window_size(self):
        return {"width": self.width, "height": self.height}

    def save_screenshot(self, _path):
        pass


def test_capture_uses_figma_baseline_dimensions(tmp_path, monkeypatch):
    driver = CaptureDriver()
    capture = ScreenshotCapture(page_data_load_wait=0)
    monkeypatch.setattr("core.screenshot.time.sleep", lambda _seconds: None)
    monkeypatch.setattr(
        capture,
        "_expand_height_until_no_vertical_scroll",
        lambda **kwargs: kwargs["initial_height"],
    )

    capture.capture(
        "https://example.com",
        str(tmp_path / "shot.png"),
        width=1440,
        height=900,
        figma_image_width=1920,
        figma_image_height=3166,
        driver=driver,
    )

    assert driver.window_sizes[0] == (1920, 3166)
