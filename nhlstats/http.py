"""Yhteinen HTTP-istunto uudelleenyrityksillä ja kohteliaalla viiveellä."""
import time

import requests

from .config import REQUEST_DELAY, USER_AGENT

session = requests.Session()
session.headers["User-Agent"] = USER_AGENT

RETRY_STATUSES = {429, 500, 502, 503, 504}


def get(url: str, retries: int = 4) -> requests.Response:
    for attempt in range(retries):
        try:
            resp = session.get(url, timeout=60)
        except requests.RequestException:
            if attempt == retries - 1:
                raise
        else:
            if resp.status_code not in RETRY_STATUSES:
                resp.raise_for_status()
                time.sleep(REQUEST_DELAY)
                return resp
            if attempt == retries - 1:
                resp.raise_for_status()
        time.sleep(2 ** attempt * 2)
    raise RuntimeError(f"Haku epäonnistui: {url}")
