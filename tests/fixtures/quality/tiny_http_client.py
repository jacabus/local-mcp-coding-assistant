"""Tiny HTTP client: HTTP may be cited only because it is present."""

from urllib.request import urlopen


def fetch_text(url: str) -> str:
    # Caller passes a full URL such as http://example.com/path
    with urlopen(url, timeout=5) as response:
        return response.read().decode("utf-8", errors="replace")
