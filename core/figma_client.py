"""
Figma API client for fetching design JSON data.
"""

import requests
from typing import Optional

from .logging_config import get_logger

logger = get_logger("core.figma_client")


class FigmaClient:
    """Fetches Figma file JSON data using the REST API."""

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
