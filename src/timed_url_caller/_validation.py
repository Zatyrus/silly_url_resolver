"""Input validation before any browser action. No hostname allowlist for targets."""

from urllib.parse import urlsplit


def validate_url(url):
    if not isinstance(url, str) or not url or len(url) > 8192:
        raise ValueError("Enter an absolute HTTP(S) URL of at most 8192 characters.")
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url) or "\\" in url:
        raise ValueError("The URL contains whitespace or a backslash; use URL encoding.")
    if any(0xD800 <= ord(c) <= 0xDFFF for c in url):
        raise ValueError("The URL contains invalid Unicode characters; check the copied address.")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise ValueError("The URL has an invalid hostname or port.") from exc
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("Enter a complete http:// or https:// URL.")
    if parts.username is not None or parts.password is not None:
        raise ValueError("Remove credentials from the URL; sign in through the browser.")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("The URL port must be between 1 and 65535.")
    return url


def validate_endpoint(value):
    validate_url(value)
    parts = urlsplit(value)
    if (
        parts.scheme != "http"
        or parts.hostname != "127.0.0.1"
        or parts.port is None
        or parts.path not in ("", "/")
        or parts.query
        or parts.fragment
    ):
        raise ValueError(
            "The browser control address must look like http://127.0.0.1:9222. This restriction does not apply to the destination URL."
        )
    return value.rstrip("/")
