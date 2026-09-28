"""
Figma API client for fetching design metadata and exported node images.
"""

import time
from pathlib import Path
from typing import Optional, Union

from pathlib import Path
from typing import Optional

import requests

from .logging_config import get_logger

logger = get_logger("core.figma_client")


class FigmaClient:
    """Fetches Figma file JSON data and node exports using the REST API."""

    BASE_URL = "https://api.figma.com/v1"
    MAX_RETRIES = 4
    RETRY_BACKOFF_SECONDS = 2

    def __init__(self, access_token: str):
        if not access_token:
            raise ValueError("Figma access token must not be empty.")
        self.headers = {"X-Figma-Token": access_token}

    def fetch_file_data(self, file_id: str) -> dict:
        """
        Fetch complete Figma file JSON data.

        Logs fetch progress and any errors encountered.

        Args:
            file_id: Figma file key (from the file URL).

        Returns:
            The Figma file JSON data as a dictionary.
        """
        logger.debug(f"Fetching Figma file data: file_id={file_id}")

        url = f"{self.BASE_URL}/files/{file_id}"
        resp = self._request_with_retries(url, headers=self.headers, timeout=30)
        payload = resp.json()
        logger.debug(f"Figma API response status: {resp.status_code}")

        if payload.get("err"):
            error_msg = f"Figma API returned error: {payload['err']}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        logger.info(f"Figma file data fetched successfully: {file_id}")
        return payload

    def download_node_image(
        self,
        file_id: str,
        node_id: str,
        output_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """Download a PNG for the requested Figma node and save it to disk."""
        if not file_id:
            raise ValueError("Figma file id must not be empty.")
        if not node_id:
            raise ValueError("Figma node id must not be empty.")

        target_path = Path(output_path) if output_path else Path(f"{file_id}_{node_id}.png")
        target_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Downloading Figma node image: file_id={file_id}, node_id={node_id}")
        url = f"{self.BASE_URL}/images/{file_id}"
        params = {"ids": node_id, "format": "png", "scale": 2}
        resp = self._request_with_retries(url, headers=self.headers, params=params, timeout=60)

        payload = resp.json()
        if payload.get("err"):
            error_msg = f"Figma image export returned error: {payload['err']}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        images = payload.get("images") or {}
        image_url = None
        for candidate in self._candidate_node_ids(node_id):
            if candidate in images and images[candidate]:
                image_url = images[candidate]
                break

        if not image_url:
            error_msg = f"Figma API did not return an image URL for node_id={node_id}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        logger.debug(f"Figma image export URL resolved: {image_url}")
        image_resp = self._request_with_retries(image_url, timeout=60, allow_json=False)
        target_path.write_bytes(image_resp.content)

        logger.info(f"Figma node image saved successfully: {target_path}")
        return str(target_path)

    def _request_with_retries(
        self,
        url: str,
        *,
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
        timeout: int = 30,
        allow_json: bool = True,
    ) -> requests.Response:
        last_error: Optional[Exception] = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=timeout)
                if resp.status_code == 429 and attempt < self.MAX_RETRIES:
                    wait_seconds = self.RETRY_BACKOFF_SECONDS * (attempt + 1)
                    logger.warning(
                        "Figma API rate limit hit; retrying in %ss (attempt %d/%d)",
                        wait_seconds,
                        attempt + 1,
                        self.MAX_RETRIES,
                    )
                    time.sleep(wait_seconds)
                    continue
                resp.raise_for_status()
                return resp
            except requests.HTTPError as exc:
                last_error = exc
                if exc.response is not None and exc.response.status_code == 429 and attempt < self.MAX_RETRIES:
                    wait_seconds = self.RETRY_BACKOFF_SECONDS * (attempt + 1)
                    logger.warning(
                        "Figma API rate limit hit; retrying in %ss (attempt %d/%d)",
                        wait_seconds,
                        attempt + 1,
                        self.MAX_RETRIES,
                    )
                    time.sleep(wait_seconds)
                    continue
                raise
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.MAX_RETRIES:
                    wait_seconds = self.RETRY_BACKOFF_SECONDS * (attempt + 1)
                    logger.warning(
                        "Figma request failed; retrying in %ss (attempt %d/%d): %s",
                        wait_seconds,
                        attempt + 1,
                        self.MAX_RETRIES,
                        exc,
                    )
                    time.sleep(wait_seconds)
                    continue
                raise

        if last_error is not None:
            raise last_error
        raise RuntimeError("Figma request failed without a captured exception")

    @staticmethod
    def _candidate_node_ids(node_id: str) -> list[str]:
        values = [node_id]
        if ":" in node_id:
            values.append(node_id.replace(":", "-"))
        if "-" in node_id:
            values.append(node_id.replace("-", ":"))
        return list(dict.fromkeys(values))

    def get_file_info(self, file_id: str) -> dict:
        """Fetch basic metadata for a Figma file (title, last-modified, etc.)."""
        url = f"{self.BASE_URL}/files/{file_id}"
        resp = requests.get(url, headers=self.headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_node_image_url(
        self,
        file_id: str,
        node_id: str,
        image_format: str = "png",
        scale: float = 1.0,
    ) -> str:
        """
        Resolve a temporary export URL for a specific Figma node image.

        Args:
            file_id: Figma file key.
            node_id: Node id inside the file (for example "3254:8491").
            image_format: Export format supported by Figma images API.
            scale: Optional export scale multiplier.

        Returns:
            A signed URL pointing to the exported image.
        """
        if not file_id or not str(file_id).strip():
            raise ValueError("Figma file_id must not be empty for node export.")
        if not node_id or not str(node_id).strip():
            raise ValueError("Figma node_id must not be empty for node export.")

        params = {
            "ids": str(node_id).strip(),
            "format": image_format,
        }
        if scale and scale != 1.0:
            params["scale"] = scale

        url = f"{self.BASE_URL}/images/{str(file_id).strip()}"
        resp = requests.get(url, headers=self.headers, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()

        if payload.get("err"):
            error_msg = f"Figma images API returned error: {payload['err']}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        images = payload.get("images") or {}
        image_url = images.get(str(node_id).strip())
        if not image_url:
            raise RuntimeError(
                "Figma did not return an export image URL for "
                f"file_id={file_id}, node_id={node_id}"
            )
        return image_url

    def download_node_image(
        self,
        file_id: str,
        node_id: str,
        output_path: str,
        image_format: str = "png",
        scale: float = 1.0,
    ) -> str:
        """
        Download a Figma node export and save it locally.

        Returns:
            Absolute path to saved image.
        """
        image_url = self.get_node_image_url(
            file_id=file_id,
            node_id=node_id,
            image_format=image_format,
            scale=scale,
        )

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        img_resp = requests.get(image_url, timeout=60)
        img_resp.raise_for_status()
        out.write_bytes(img_resp.content)

        saved_path = str(out.resolve())
        logger.info(
            "Figma node image downloaded successfully: "
            f"file_id={file_id}, node_id={node_id}, output={saved_path}"
        )
        return saved_path
