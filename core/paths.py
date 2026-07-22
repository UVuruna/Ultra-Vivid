"""Path resolution — the single place that knows where things live.

Two modes, so the exact same code runs from the repo AND as a frozen
single-exe installed to Program Files:

- REPO (not frozen): everything lives in the project folder, exactly as
  before — config.json, logs/, shortcuts/, data/, assets/ side by side.
- FROZEN (PyInstaller): read-only bundled data (world DB, assets) comes
  from the temporary extraction dir (sys._MEIPASS); WRITABLE state
  (config.json, logs/, shortcuts/) lives under the per-user LOCALAPPDATA
  UltraVivid folder, seeded once from the bundled default config. Program
  Files is not writable by a standard user, so state must never live there.
"""

import os
import shutil
import sys
from pathlib import Path

IS_FROZEN = getattr(sys, "frozen", False)

# Read-only resources: the bundle when frozen, the repo otherwise.
if IS_FROZEN:
    BUNDLE_DIR = Path(sys._MEIPASS)
    _local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    DATA_DIR = Path(_local) / "UltraVivid"
else:
    BUNDLE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BUNDLE_DIR

# Writable state
CONFIG_PATH = DATA_DIR / "config.json"
LOG_DIR = DATA_DIR / "logs"
STATE_PATH = LOG_DIR / "state.json"
SLOTS_DIR = DATA_DIR / "shortcuts"

# Read-only bundled resources
WORLD_DB = BUNDLE_DIR / "data" / "world_locations.json"
ASSETS_DIR = BUNDLE_DIR / "assets"
DEFAULT_CONFIG = BUNDLE_DIR / "config.json"       # shipped default (seed)


def ensure_state() -> None:
    """Create the writable state dir and seed config.json on first frozen
    run. No-op in repo mode (files already there)."""
    if not IS_FROZEN:
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    if not CONFIG_PATH.exists() and DEFAULT_CONFIG.exists():
        shutil.copy2(DEFAULT_CONFIG, CONFIG_PATH)


def launcher_command(*args: str) -> list[str]:
    """Command that re-invokes this program with the given CLI args.

    Frozen: the exe itself understands the flags (single-exe dispatch).
    Repo:   run resolver.py with the interpreter.
    """
    if IS_FROZEN:
        return [sys.executable, *args]
    return [sys.executable, str(BUNDLE_DIR / "resolver.py"), *args]


def slot_command_string(shortcut_spec: str) -> str:
    """The command a slot VBS runs (already quoted for WScript.Shell.Run)."""
    if IS_FROZEN:
        return f'""{sys.executable}"" --shortcut ""{shortcut_spec}""'
    pythonw = Path(sys.executable).parent / "pythonw.exe"
    resolver = BUNDLE_DIR / "resolver.py"
    return f'""{pythonw}"" ""{resolver}"" --shortcut ""{shortcut_spec}""'
