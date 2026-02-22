# config_writer.py - Write config.json from GUI state

import json
import os


def write_config(config_path: str, state: dict) -> None:
    """Write config.json from GUI state dict.

    state format:
    {
        "openRGBPath": "C:\\...\\OpenRGB.exe",
        "schedules": [
            {"taskName": "OpenRGB zora", "vbsName": "1-dawn", "profile": "1-blue", "startTime": "03:00"},
            ...
        ],
        "extras": [
            {"vbsName": "light", "profile": "9-white"},
            ...
        ],
        "rainbow": [
            {"vbsName": "F1", "profile": "UC-01-00F"},
            ...
        ]
    }
    """
    config = {
        "openRGBPath": state["openRGBPath"],
        "schedules": {
            "items": state["schedules"]
        },
        "extras": state["extras"],
        "rainbow": {
            "startHour": 3,
            "items": state["rainbow"]
        }
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def read_config(config_path: str) -> dict | None:
    """Read config.json and return GUI state dict, or None if file missing."""
    if not os.path.isfile(config_path):
        return None
    with open(config_path, encoding="utf-8") as f:
        raw = json.load(f)

    # Handle both old schema (startHour) and new schema (startTime per item)
    schedule_items = raw.get("schedules", {}).get("items", [])
    start_hour = raw.get("schedules", {}).get("startHour", 3)
    count = len(schedule_items)
    duration = 24 // count if count else 3

    schedules = []
    for i, item in enumerate(schedule_items):
        if "startTime" in item:
            start_time = item["startTime"]
        else:
            # Migrate old schema: calculate from startHour
            hour = (start_hour + duration * i) % 24
            start_time = f"{hour:02d}:00"
        schedules.append({
            "taskName": item.get("taskName", ""),
            "vbsName": item.get("vbsName", ""),
            "profile": item.get("profile", ""),
            "startTime": start_time,
        })

    return {
        "openRGBPath": raw.get("openRGBPath", ""),
        "schedules": schedules,
        "extras": raw.get("extras", []),
        "rainbow": raw.get("rainbow", {}).get("items", []),
    }
