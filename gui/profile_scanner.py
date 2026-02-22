# profile_scanner.py - Scan OpenRGB .orp profile files

import os


def scan_profiles(openrgb_exe_path: str) -> list[str]:
    """Return sorted list of profile names found near OpenRGB installation."""
    candidates = _get_candidate_dirs(openrgb_exe_path)
    for folder in candidates:
        profiles = _scan_dir(folder)
        if profiles:
            return profiles
    return []


def _get_candidate_dirs(openrgb_exe_path: str) -> list[str]:
    appdata = os.environ.get("APPDATA", "")
    return [
        os.path.join(appdata, "OpenRGB"),
        os.path.dirname(openrgb_exe_path),
    ]


def _scan_dir(folder: str) -> list[str]:
    if not os.path.isdir(folder):
        return []
    names = [
        os.path.splitext(f)[0]
        for f in os.listdir(folder)
        if f.lower().endswith(".orp")
    ]
    return sorted(names)
