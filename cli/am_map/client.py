"""Thin HTTP client the CLI uses to talk to the backend (section 4). The CLI
never touches the acquisition/ML/mapping code directly -- it's just another
consumer of the same REST API the web dashboard uses."""
from __future__ import annotations

import os

import httpx

DEFAULT_BASE_URL = os.environ.get("AM_MAP_API_URL", "http://localhost:8000")
DEFAULT_API_TOKEN = os.environ.get("AM_MAP_API_TOKEN") or os.environ.get("API_TOKEN") or ""


class ApiError(RuntimeError):
    pass


class Client:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 15.0,
        api_token: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        token = api_token if api_token is not None else DEFAULT_API_TOKEN
        headers = {}
        if token:
            headers["X-API-Token"] = token
        self._client = httpx.Client(
            base_url=self.base_url, timeout=timeout, headers=headers
        )

    def _handle(self, resp: httpx.Response):
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise ApiError(
                f"{resp.status_code} {resp.request.method} {resp.request.url}: {detail}"
            )
        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            return resp.json()
        if content_type.startswith("text/"):
            return resp.text
        return resp.content

    def get(self, path: str, **params):
        try:
            return self._handle(self._client.get(path, params=params))
        except httpx.ConnectError as e:
            raise ApiError(
                f"Could not reach Am the Map backend at {self.base_url}. "
                f"Is it running? (see docs/installation.md)"
            ) from e

    def post(self, path: str, json: dict | None = None, **params):
        try:
            return self._handle(self._client.post(path, json=json or {}, params=params))
        except httpx.ConnectError as e:
            raise ApiError(
                f"Could not reach Am the Map backend at {self.base_url}."
            ) from e

    def put(self, path: str, json: dict | None = None):
        try:
            return self._handle(self._client.put(path, json=json or {}))
        except httpx.ConnectError as e:
            raise ApiError(
                f"Could not reach Am the Map backend at {self.base_url}."
            ) from e

    def delete(self, path: str):
        try:
            return self._handle(self._client.delete(path))
        except httpx.ConnectError as e:
            raise ApiError(
                f"Could not reach Am the Map backend at {self.base_url}."
            ) from e
