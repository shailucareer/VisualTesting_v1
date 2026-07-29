"""
Figma API client for fetching design metadata and exported node images.
"""

from pathlib import Path
from typing import Optional

import requests

from .logging_config import get_logger

logger = get_logger("core.figma_client")


class FigmaClient:
    """Fetches Figma file JSON data and node exports using the REST API."""

    BASE_URL = "https://api.figma.com/v1"

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
        resp = requests.get(url, headers=self.headers, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        logger.debug(f"Figma API response status: {resp.status_code}")

        if payload.get("err"):
            error_msg = f"Figma API returned error: {payload['err']}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        logger.info(f"Figma file data fetched successfully: {file_id}")
        return payload

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
