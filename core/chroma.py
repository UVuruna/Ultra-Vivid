"""Razer Chroma REST client — keyboard coloring WITHOUT touching Synapse.

Talks to the local Chroma SDK endpoint (installed with Synapse). Lighting
and key bindings are separate subsystems at Razer: a Chroma session
"claims" the keyboard's lighting while active, Synapse bindings keep
working untouched.

A Chroma session dies without a heartbeat (~every few seconds), so this
client is held by the RESIDENT daemon — a one-shot process cannot keep a
color on the keyboard. Standard library only (urllib), no extra deps.
"""

import json
import logging
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

CHROMA_URL = "http://localhost:54235/razer/chromasdk"
HEARTBEAT_SECONDS = 5.0
_TIMEOUT = 3.0

_APP_INFO = {
    "title": "Ultra Vivid",
    "description": "Scheduled RGB colors following the Ultra Vivid presets",
    "author": {"name": "UVuruna", "contact": "https://github.com/UVuruna"},
    "device_supported": ["keyboard"],
    "category": "application",
}


class ChromaError(Exception):
    """Chroma endpoint unreachable or rejected a request."""


def _request(method: str, url: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            body = resp.read()
            return json.loads(body) if body else {}
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        raise ChromaError(f"{method} {url}: {e}") from e


class ChromaSession:
    """One initialized Chroma session. Call heartbeat() at least every
    ~10 s (daemon uses HEARTBEAT_SECONDS) or the session dies."""

    def __init__(self):
        result = _request("POST", CHROMA_URL, _APP_INFO)
        if "uri" not in result:
            raise ChromaError(f"Chroma init rejected: {result}")
        self.uri: str = result["uri"]
        logger.info("Chroma session opened: %s", self.uri)

    def heartbeat(self) -> None:
        _request("PUT", f"{self.uri}/heartbeat")

    def set_keyboard_color(self, hex_color: str) -> None:
        """Static whole-keyboard color. Chroma wants a BGR-packed int."""
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        bgr = (b << 16) | (g << 8) | r
        _request("PUT", f"{self.uri}/keyboard",
                 {"effect": "CHROMA_STATIC", "param": {"color": bgr}})

    def close(self) -> None:
        try:
            _request("DELETE", self.uri)
            logger.info("Chroma session closed.")
        except ChromaError as e:
            logger.warning("Chroma close failed (session may be dead): %s", e)
