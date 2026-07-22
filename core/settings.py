"""Load and validate config.json (schema v2).

Validation fails loudly (Rule #1): a broken config must never half-run
the resolver — every error names the exact field that is wrong.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_VERSION = 2

WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
MONTH_KEYS = ["jan", "feb", "mar", "apr", "may", "jun",
              "jul", "aug", "sep", "oct", "nov", "dec"]
SCHEDULE_TYPES = ["hours", "weekdays", "monthdays", "months", "daylight"]
SHORTCUT_SELECTORS = ["shift", "ctrl", "alt", "ctrl+shift", "alt+shift",
                      "ctrl+alt", "hypershift"]


class ConfigError(Exception):
    """Raised when config.json is missing, unreadable, or invalid."""


@dataclass(frozen=True)
class OpenRGBSettings:
    host: str
    port: int
    connect_retries: int
    retry_seconds: float


@dataclass(frozen=True)
class Location:
    name: str
    latitude: float
    longitude: float
    timezone: str


@dataclass(frozen=True)
class DeviceFilter:
    mode: str          # "exclude" | "include"
    names: list[str]   # case-insensitive substrings matched against device names


@dataclass(frozen=True)
class Schedule:
    enabled: bool
    type: str                       # one of SCHEDULE_TYPES
    hours: list[dict]               # [{"from": int, "to": int, "preset": str}]
    weekdays: dict[str, str]        # mon..sun -> preset
    monthdays: list[dict]           # [{"from": int, "to": int, "preset": str}]
    months: dict[str, str]          # jan..dec -> preset
    daylight: dict                  # {"day": [..], "twilight": str|None, "night": [..]}


@dataclass(frozen=True)
class ShortcutSet:
    name: str                # user-chosen set name (also the slot folder name)
    selector: str            # one of SHORTCUT_SELECTORS
    bindings: dict[str, str] # key label (any mix from keymap) -> preset name


@dataclass(frozen=True)
class ChromaSettings:
    """Optional Razer Chroma module: color the keyboard alongside the
    schedule WITHOUT touching Synapse key bindings (held by the daemon —
    Chroma sessions die without heartbeat, so a one-shot cannot do it)."""
    enabled: bool
    follow_schedule: bool


@dataclass(frozen=True)
class Settings:
    openrgb: OpenRGBSettings
    location: Location
    devices: DeviceFilter
    color_presets: dict[str, list[str]]  # name -> list of RRGGBB hex strings
    schedule: Schedule
    shortcuts_enabled: bool = True
    shortcut_sets: list[ShortcutSet] = field(default_factory=list)
    chroma: ChromaSettings = field(
        default_factory=lambda: ChromaSettings(False, True))


def load(config_path: Path) -> Settings:
    if not config_path.is_file():
        raise ConfigError(f"config.json not found: {config_path}")
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigError(f"config.json is not valid JSON: {e}") from e
    return parse(raw)


def parse(raw: dict) -> Settings:
    """Validate a raw config dict (the GUI validates edits through this
    before writing the file)."""
    if raw.get("version") != CONFIG_VERSION:
        raise ConfigError(
            f"config.json version is {raw.get('version')!r}, expected {CONFIG_VERSION}. "
            "Old-schema configs must be migrated (open the GUI or see README)."
        )

    presets = _parse_presets(raw)
    schedule = _parse_schedule(raw, presets)
    shortcut_sets = _parse_shortcuts(raw, presets)

    o = raw.get("openrgb", {})
    loc = raw.get("location", {})
    dev = raw.get("devices", {})
    if dev.get("mode") not in ("exclude", "include"):
        raise ConfigError('devices.mode must be "exclude" or "include"')

    return Settings(
        openrgb=OpenRGBSettings(
            host=o.get("host", "127.0.0.1"),
            port=int(o.get("port", 6742)),
            connect_retries=int(o.get("connectRetries", 30)),
            retry_seconds=float(o.get("retrySeconds", 2)),
        ),
        location=Location(
            name=loc.get("name", ""),
            latitude=float(loc["latitude"]),
            longitude=float(loc["longitude"]),
            timezone=loc["timezone"],
        ) if loc else Location("", 0.0, 0.0, ""),
        devices=DeviceFilter(mode=dev["mode"], names=list(dev.get("names", []))),
        color_presets=presets,
        schedule=schedule,
        shortcuts_enabled=bool(raw.get("shortcuts", {}).get("enabled", True)),
        shortcut_sets=shortcut_sets,
        chroma=ChromaSettings(
            enabled=bool(raw.get("chroma", {}).get("enabled", False)),
            follow_schedule=bool(raw.get("chroma", {}).get("followSchedule", True)),
        ),
    )


def _parse_presets(raw: dict) -> dict[str, list[str]]:
    presets = raw.get("colorPresets")
    if not isinstance(presets, dict) or not presets:
        raise ConfigError("colorPresets must be a non-empty object {name: [RRGGBB, ...]}")
    for name, colors in presets.items():
        if not isinstance(colors, list) or not colors:
            raise ConfigError(f"colorPresets[{name!r}] must be a non-empty list of hex colors")
        for c in colors:
            if not (isinstance(c, str) and len(c) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in c)):
                raise ConfigError(f"colorPresets[{name!r}]: {c!r} is not RRGGBB hex")
    return presets


def _require_preset(presets: dict, name: str, where: str) -> None:
    if name not in presets:
        raise ConfigError(f"{where} references unknown color preset {name!r}")


def _parse_schedule(raw: dict, presets: dict) -> Schedule:
    s = raw.get("schedule", {})
    stype = s.get("type")
    if stype not in SCHEDULE_TYPES:
        raise ConfigError(f"schedule.type must be one of {SCHEDULE_TYPES}, got {stype!r}")

    hours = s.get("hours", [])
    weekdays = s.get("weekdays", {})
    monthdays = s.get("monthdays", [])
    months = s.get("months", {})
    daylight = s.get("daylight", {})

    if stype == "hours":
        for slot in hours:
            if not (0 <= slot["from"] <= 23 and 0 <= slot["to"] <= 23):
                raise ConfigError(f"schedule.hours slot {slot}: hours must be 0-23")
            _require_preset(presets, slot["preset"], "schedule.hours")
    elif stype == "weekdays":
        missing = [k for k in WEEKDAY_KEYS if k not in weekdays]
        if missing:
            raise ConfigError(f"schedule.weekdays must cover all 7 days; missing: {missing}")
        for k in WEEKDAY_KEYS:
            _require_preset(presets, weekdays[k], f"schedule.weekdays.{k}")
    elif stype == "monthdays":
        for slot in monthdays:
            if not (1 <= slot["from"] <= 31 and 1 <= slot["to"] <= 31 and slot["from"] <= slot["to"]):
                raise ConfigError(f"schedule.monthdays slot {slot}: needs 1 <= from <= to <= 31")
            _require_preset(presets, slot["preset"], "schedule.monthdays")
    elif stype == "months":
        missing = [k for k in MONTH_KEYS if k not in months]
        if missing:
            raise ConfigError(f"schedule.months must cover all 12 months; missing: {missing}")
        for k in MONTH_KEYS:
            _require_preset(presets, months[k], f"schedule.months.{k}")
    elif stype == "daylight":
        day = daylight.get("day", [])
        if not day:
            raise ConfigError("schedule.daylight.day must list at least one preset")
        for name in day:
            _require_preset(presets, name, "schedule.daylight.day")
        twilight = daylight.get("twilight")
        if twilight is not None:
            _require_preset(presets, twilight, "schedule.daylight.twilight")
        for name in daylight.get("night", []):
            _require_preset(presets, name, "schedule.daylight.night")
        loc = raw.get("location", {})
        if "latitude" not in loc or "longitude" not in loc or "timezone" not in loc:
            raise ConfigError("schedule.type=daylight requires location.latitude/longitude/timezone")

    return Schedule(
        enabled=bool(s.get("enabled", True)),
        type=stype,
        hours=hours, weekdays=weekdays, monthdays=monthdays,
        months=months, daylight=daylight,
    )


def _parse_shortcuts(raw: dict, presets: dict) -> list[ShortcutSet]:
    from core.keymap import VIRTUAL_KEYS

    sets = []
    names: set[str] = set()
    for i, s in enumerate(raw.get("shortcuts", {}).get("sets", [])):
        name = (s.get("name") or "").strip()
        if not name:
            raise ConfigError(f"shortcuts.sets[{i}] needs a non-empty name")
        if name.lower() in names:
            raise ConfigError(f"shortcuts.sets[{i}]: duplicate set name {name!r}")
        names.add(name.lower())
        if s.get("selector") not in SHORTCUT_SELECTORS:
            raise ConfigError(f"shortcuts.sets[{i}].selector must be one of {SHORTCUT_SELECTORS}")
        bindings = s.get("bindings", {})
        for key, preset in bindings.items():
            if key not in VIRTUAL_KEYS:
                raise ConfigError(f"shortcuts.sets[{i}]: unknown key {key!r}")
            _require_preset(presets, preset, f"shortcuts.sets[{i}].bindings[{key!r}]")
        sets.append(ShortcutSet(name=name, selector=s["selector"], bindings=bindings))
    return sets
