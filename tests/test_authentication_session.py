from core.runner import TestCase as VisualTestCase
from core.runner import TestRunner as VisualTestRunner
from core.screenshot import ScreenshotCapture


class FailingNavigationDriver:
    def __init__(self):
        self.quit_called = False

    def set_page_load_timeout(self, _timeout):
        raise RuntimeError("navigation setup failed")

    def quit(self):
        self.quit_called = True


class FakeDriver:
    def quit(self):
        pass


def test_capture_does_not_quit_caller_owned_driver(tmp_path):
    driver = FailingNavigationDriver()
    capture = ScreenshotCapture()

    try:
        capture.capture("https://example.com", str(tmp_path / "shot.png"), driver=driver)
    except RuntimeError as exc:
        assert str(exc) == "navigation setup failed"
    else:
        raise AssertionError("Expected the fake navigation setup to fail")

    assert not driver.quit_called


def test_capture_quits_driver_it_created(tmp_path, monkeypatch):
    driver = FailingNavigationDriver()
    capture = ScreenshotCapture()
    monkeypatch.setattr(capture, "create_driver", lambda *_args: driver)

    try:
        capture.capture("https://example.com", str(tmp_path / "shot.png"))
    except RuntimeError as exc:
        assert str(exc) == "navigation setup failed"
    else:
        raise AssertionError("Expected the fake navigation setup to fail")

    assert driver.quit_called


def test_project_authenticate_hook_runs_on_shared_driver(tmp_path, monkeypatch):
    driver = FakeDriver()

    class FakeCapture:
        def __init__(self, **_kwargs):
            pass

        def create_driver(self, _width, _height):
            return driver

    auth_file = tmp_path / "auth.py"
    auth_file.write_text(
        "def authenticate(driver):\n"
        "    driver.authenticated = True\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("core.runner.ScreenshotCapture", FakeCapture)

    runner = object.__new__(VisualTestRunner)
    runner.capture_screenshots = True
    runner.run_mode = "selected"
    runner.project_path = tmp_path
    runner.project = tmp_path.name
    runner.browser = "chrome"
    runner.headless = True
    runner.dpr = 1.0
    runner.page_load_timeout = 30
    test_case = VisualTestCase(
        name="home",
        run=True,
        device="Desktop",
        figma_file_name="home.png",
        url="https://example.com",
    )

    session_driver, error = runner._start_browser_session([test_case])

    assert session_driver is driver
    assert driver.authenticated
    assert error is None
