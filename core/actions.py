"""Shortcut binding actions — shared by the resolver (Synapse slots)
and the hotkey daemon (Rule #5), so both trigger paths behave the same.

A binding is either:
    {"color": name}   -> apply that color, nothing else changes
    {"preset": name}  -> SWITCH the active preset (persisted to
                         config.json so the scheduled tick keeps
                         following it), then apply whatever that preset
                         resolves to right now
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from core import schedule
from core import settings as settings_mod

logger = logging.getLogger(__name__)


def resolve_binding(config_path: Path, binding: dict) -> str | None:
    """Return the color name to apply now; persists activePreset for
    preset bindings. None means all-off (e.g. the switched-to preset
    has no slot for the current time)."""
    if "color" in binding:
        return binding["color"]

    preset_name = binding["preset"]
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    if raw.get("activePreset") != preset_name:
        raw["activePreset"] = preset_name
        config_path.write_text(
            json.dumps(raw, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
        logger.info("Active preset switched to %r", preset_name)

    cfg = settings_mod.parse(raw)
    # The press should always SHOW the preset, even while the scheduled
    # tick is globally disabled — resolve with the flag forced on.
    import dataclasses
    forced = dataclasses.replace(cfg, schedule_enabled=True)
    now = datetime.now(schedule.tick_timezone(forced))
    return schedule.resolve(forced, now)
