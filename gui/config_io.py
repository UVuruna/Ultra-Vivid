"""Read/write config.json for the GUI.

The GUI edits the RAW dict (round-trip safe: unknown future keys survive).
Saving validates through core.settings.parse first — an invalid edit never
reaches the file (Rule #1).
"""

import json
from pathlib import Path

from core import settings as settings_mod

PROJECT_DIR = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_DIR / "config.json"


def load_raw() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_raw(raw: dict) -> None:
    """Validate, then write. Raises core.settings.ConfigError on bad edits."""
    settings_mod.parse(raw)
    CONFIG_PATH.write_text(
        json.dumps(raw, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
