"""Update discovery via GitHub Releases (the project's GIT RELEASE artifacts).

Monorepo standard (root CLAUDE.md): the LAST released version on GitHub is
the source of truth; the running app checks it and offers an UPDATE when a
newer release exists. `check()` compares the latest release tag of the
project's repo against the running version and returns an Update, else None.

Callers own the UX (the GUI shows an in-window Update button: download the
installer, launch it, quit so it can replace files in use).

A repo with no releases yet and plain network failures are NORMAL outcomes
(check() returns None then) — logged at info, never raised: the app must
start fine offline.
"""

import json
import logging
import re
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)

TIMEOUT_S = 10


def app_version() -> str:
    """The running app's version. 'dev' in an unpackaged/odd checkout."""
    try:
        from version import __version__
        return __version__
    except Exception:
        try:
            from core import paths
            text = (paths.BUNDLE_DIR / "version.py").read_text(encoding="utf-8")
            match = re.search(r'__version__\s*=\s*["\'](.+?)["\']', text)
            return match.group(1) if match else "dev"
        except Exception:
            return "dev"


@dataclass(frozen=True)
class Update:
    version: str               # e.g. "0.1.230"
    installer_url: str | None  # direct Setup.exe asset, if the release has one
    page_url: str              # release page — fallback when there is no asset


def _numbers(version: str) -> tuple[int, ...]:
    """'v0.1.23' / '0.1.230' -> (0, 1, 23); () when nothing numeric (dev)."""
    return tuple(int(p) for p in re.findall(r"\d+", version)[:3])


def check(repo: str, enabled: bool = True) -> Update | None:
    """None = up to date, disabled, dev run, no releases yet, or unreachable."""
    if not enabled or not repo:
        return None
    current = _numbers(app_version())
    if not current:
        return None  # dev checkout — nothing meaningful to compare
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            data = json.loads(response.read())
    except Exception as e:  # offline / rate-limited / no releases yet (404)
        logger.info("Update check skipped: %s", e)
        return None
    latest = _numbers(data.get("tag_name") or "")
    if not latest or latest <= current:
        return None
    installer = next(
        (a.get("browser_download_url") for a in data.get("assets", [])
         if a.get("name", "").lower().endswith(".exe")),
        None,
    )
    version = ".".join(str(n) for n in latest)
    logger.info("Update available: v%s (running v%s)", version, app_version())
    return Update(version, installer,
                  data.get("html_url") or f"https://github.com/{repo}/releases")
