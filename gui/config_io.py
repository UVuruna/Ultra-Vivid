"""Read/write config.json for the GUI.

The GUI edits the RAW dict (round-trip safe: unknown future keys survive).
Saving validates through core.settings.parse first — an invalid edit never
reaches the file (Rule #1).
"""

import json

from core import paths
from core import settings as settings_mod

CONFIG_PATH = paths.CONFIG_PATH


def load_raw() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_raw(raw: dict) -> None:
    """Validate, then write. Raises core.settings.ConfigError on bad edits."""
    settings_mod.parse(raw)
    CONFIG_PATH.write_text(
        json.dumps(raw, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
