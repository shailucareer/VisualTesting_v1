from pathlib import Path

import requests

from core.figma_client import FigmaClient


class DummyResponse:
    def __init__(self, payload=None, content=b"", status_code=200):
        self._payload = payload
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_download_node_png_writes_file(tmp_path, monkeypatch):
    captured = {}

    def fake_get(url, headers=None, timeout=30, params=None, **kwargs):
        captured.setdefault("calls", []).append((url, params))
        if url.endswith("/images/file-id"):
            return DummyResponse({"images": {"node-id": "https://example.com/export.png"}})
        if url == "https://example.com/export.png":
            return DummyResponse(content=b"fake-png-bytes")
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr("core.figma_client.requests.get", fake_get)

    client = FigmaClient("figd_test_token")
    output_path = tmp_path / "downloaded.png"

    result = client.download_node_image("file-id", "node-id", output_path=output_path)

    assert result == str(output_path)
    assert output_path.exists()
    assert output_path.read_bytes() == b"fake-png-bytes"
    assert captured["calls"][0][1]["ids"] == "node-id"


def test_download_node_png_retries_after_rate_limit(tmp_path, monkeypatch):
    calls = []
    first_call = True

    def fake_get(url, headers=None, timeout=30, params=None, **kwargs):
        nonlocal first_call
        calls.append((url, params))
        if first_call:
            first_call = False
            response = DummyResponse(payload=None, content=b"", status_code=429)
            response.raise_for_status = lambda: (_ for _ in ()).throw(requests.HTTPError(response=response))
            return response
        if url.endswith("/images/file-id"):
            return DummyResponse({"images": {"node-id": "https://example.com/export.png"}})
        if url == "https://example.com/export.png":
            return DummyResponse(content=b"fake-png-bytes")
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr("core.figma_client.requests.get", fake_get)
    monkeypatch.setattr("core.figma_client.time.sleep", lambda *_: None)

    client = FigmaClient("figd_test_token")
    output_path = tmp_path / "retried.png"

    result = client.download_node_image("file-id", "node-id", output_path=output_path)

    assert result == str(output_path)
    assert output_path.exists()
    assert output_path.read_bytes() == b"fake-png-bytes"
    assert len(calls) >= 2
