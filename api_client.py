import logging
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger("api_client")

# How many times to retry a failed POST before giving up
_MAX_RETRIES   = 3
_BACKOFF_FACTOR = 0.5   # wait 0.5 s, 1 s, 2 s between retries
_TIMEOUT       = 5      # seconds per request


def _build_session(api_key: str) -> requests.Session:
    """Build a requests Session with retry logic and auth header baked in."""
    session = requests.Session()
    session.headers.update({
        "X-API-Key":    api_key,
        "Content-Type": "application/json",
        "Accept":       "application/json",
    })

    retry_strategy = Retry(
        total=_MAX_RETRIES,
        backoff_factor=_BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://",  adapter)
    session.mount("https://", adapter)
    return session


class APIClient:
    """
    Thin wrapper around requests that targets the Smart Classroom FastAPI backend.

    Usage:
        client = APIClient(base_url="http://127.0.0.1:8000", api_key="secret")
        client.post("/attendance", {"student_id": "42", "method": "rfid"})
        data = client.get("/timetable/today")
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._session = _build_session(api_key)

    # ─────────────────────────────────────────
    # Public methods
    # ─────────────────────────────────────────
    def post(self, path: str, payload: dict[str, Any]) -> dict | None:
        """
        POST JSON payload to the backend.
        Returns parsed JSON response dict, or None on failure.
        """
        url = self._url(path)
        log.debug("POST %s  payload=%r", url, payload)
        try:
            response = self._session.post(url, json=payload, timeout=_TIMEOUT)
            return self._handle_response(response, "POST", path)
        except requests.exceptions.ConnectionError:
            log.error("Connection refused — is FastAPI running at %s?", self.base_url)
        except requests.exceptions.Timeout:
            log.error("Timeout on POST %s (waited %d s)", path, _TIMEOUT)
        except requests.exceptions.RequestException as exc:
            log.error("POST %s failed: %s", path, exc)
        return None

    def get(self, path: str, params: dict | None = None) -> dict | None:
        """
        GET a resource from the backend.
        Returns parsed JSON response dict, or None on failure.
        """
        url = self._url(path)
        log.debug("GET %s  params=%r", url, params)
        try:
            response = self._session.get(url, params=params, timeout=_TIMEOUT)
            return self._handle_response(response, "GET", path)
        except requests.exceptions.ConnectionError:
            log.error("Connection refused — is FastAPI running at %s?", self.base_url)
        except requests.exceptions.Timeout:
            log.error("Timeout on GET %s (waited %d s)", path, _TIMEOUT)
        except requests.exceptions.RequestException as exc:
            log.error("GET %s failed: %s", path, exc)
        return None

    # ─────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────
    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    @staticmethod
    def _handle_response(
        response: requests.Response,
        method: str,
        path: str,
    ) -> dict | None:
        if response.status_code == 403:
            log.error(
                "%s %s returned 403 Forbidden. "
                "Check your API_KEY in .env matches the server.",
                method, path,
            )
            return None

        if response.status_code == 422:
            log.error(
                "%s %s returned 422 Unprocessable Entity. "
                "Payload schema mismatch: %s",
                method, path, response.text,
            )
            return None

        if not response.ok:
            log.error(
                "%s %s returned HTTP %d: %s",
                method, path, response.status_code, response.text[:200],
            )
            return None

        try:
            data = response.json()
            log.debug("%s %s  →  %r", method, path, data)
            return data
        except ValueError:
            log.warning(
                "%s %s returned non-JSON body: %r",
                method, path, response.text[:200],
            )
            return {"raw": response.text}