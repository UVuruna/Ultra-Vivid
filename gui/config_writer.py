# config_writer.py - Write config.json from GUI state

import json
import os
from typing import Optional


def write_config(config_path: str, state: dict) -> None:
    """Write config.json from GUI state dict.

    state format:
    {
        "openRGBPath": "C:\\...\\OpenRGB.exe",
        "schedules": {
            "enabled": True,
            "items": [
                {"taskName": "OpenRGB slot1", "vbsName": "slot1", "profile": "...", "startTime": "03:00"},
                ...
            ]
        },
        "shortcuts": {
            "enabled": True,
            "modifier": "Shift",
            "keyRow": "F",
            "items": [
                {"vbsName": "F1", "profile": "..."},
                ...
            ]
        },
        "extras": [
            {"vbsName": "light", "profile": "9-white"},
            ...
        ]
    }
    """
    config = {
        "openRGBPath": state["openRGBPath"],
        "schedules": state["schedules"],
        "shortcuts": state["shortcuts"],
        "extras": state["extras"],
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def read_config(config_path: str) -> Optional[dict]:
    """Read config.json and return GUI state dict, or None if file missing or corrupt."""
    if not os.path.isfile(config_path):
        return None
    with open(config_path, encoding="utf-8") as f:
        try:
            raw = json.load(f)
        except json.JSONDecodeError:
            return None

    # Handle both old schema (startHour) and new schema (startTime per item)
    raw_schedules = raw.get("schedules", {})
    schedule_items = raw_schedules.get("items", [])
    count = len(schedule_items)
    duration = 24 // count if count else 0

    schedules_list = []
    for i, item in enumerate(schedule_items):
        if "startTime" in item:
            start_time = item["startTime"]
        else:
            # Migrate old schema: calculate from startHour
            start_hour = raw_schedules.get("startHour", 3)
            hour = (start_hour + duration * i) % 24
            start_time = f"{hour:02d}:00"
        schedules_list.append({
            "taskName": item.get("taskName", ""),
            "vbsName": item.get("vbsName", ""),
            "profile": item.get("profile", ""),
            "startTime": start_time,
        })

    # Shortcuts section — support old "rainbow" key for backward compat
    raw_shortcuts = raw.get("shortcuts") or raw.get("rainbow", {})
    shortcuts_items = raw_shortcuts.get("items", [])

    return {
        "openRGBPath": raw.get("openRGBPath", ""),
        "schedules": {
            "enabled": raw_schedules.get("enabled", True),
            "items": schedules_list,
        },
        "shortcuts": {
            "enabled": raw_shortcuts.get("enabled", True),
            "modifier": raw_shortcuts.get("modifier", "Shift"),
            "keyRow": raw_shortcuts.get("keyRow", "F"),
            "items": shortcuts_items,
        },
        "extras": raw.get("extras", []),
    }
