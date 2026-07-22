"""Path resolution — the single place that knows where things live.

ONE config, always. Writable state (config.json, logs, state) lives under
the per-user LOCALAPPDATA UltraVivid folder in EVERY mode — repo runs and
the installed exe therefore read and write the exact same file, so an edit
in the GUI is always the edit the daemon and the Synapse slots see. (The
earlier repo-vs-LOCALAPPDATA split meant editing one config while the
running pieces read the other — edits appeared to "not apply".)

Read-only resources (the world DB, assets, the default-config seed) come
from the repo folder when running from source, or the PyInstaller bundle
(sys._MEIPASS) when frozen.

Shortcut slot files stay next to the code that generates them (repo
`shortcuts/` in dev, LOCALAPPDATA when frozen) so existing Synapse links
keep working; they call the resolver, which reads the one config above.
"""

import os
import shutil
import sys
from pathlib import Path

IS_FROZEN = getattr(sys, "frozen", False)

# Read-only resources: the bundle when frozen, the repo otherwise.
BUNDLE_DIR = Path(sys._MEIPASS) if IS_FROZEN else Path(__file__).resolve().parent.parent

# Writable state — ALWAYS per-user LOCALAPPDATA (single source of truth).
_local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
DATA_DIR = Path(_local) / "UltraVivid"

CONFIG_PATH = DATA_DIR / "config.json"
LOG_DIR = DATA_DIR / "logs"
STATE_PATH = LOG_DIR / "state.json"

# Slots live with the generating code (keeps existing Synapse links valid).
SLOTS_DIR = (DATA_DIR if IS_FROZEN else BUNDLE_DIR) / "shortcuts"

# Read-only bundled resources
WORLD_DB = BUNDLE_DIR / "data" / "world_locations.json"
ASSETS_DIR = BUNDLE_DIR / "assets"
DEFAULT_CONFIG = BUNDLE_DIR / "config.json"       # shipped default (seed)

# Windows: run child processes without flashing a console window.
_CREATE_NO_WINDOW = 0x08000000


def no_window() -> dict:
    """subprocess kwargs that suppress a console/terminal window."""
    return {"creationflags": _CREATE_NO_WINDOW} if os.name == "nt" else {}


def ensure_state() -> None:
    """Create the writable state dir and seed config.json on first run
    (any mode) from the shipped default."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    if not CONFIG_PATH.exists() and DEFAULT_CONFIG.exists():
        shutil.copy2(DEFAULT_CONFIG, CONFIG_PATH)


def launcher_command(*args: str) -> list[str]:
    """Command that re-invokes this program with the given CLI args.

    Frozen: the exe understands the flags. Repo: run main.py (the same
    dispatcher), so GUI-issued flags like --install-tasks route correctly.
    """
    if IS_FROZEN:
        return [sys.executable, *args]
    pythonw = Path(sys.executable).parent / "pythonw.exe"
    launcher = str(pythonw if pythonw.exists() else sys.executable)
    return [launcher, str(BUNDLE_DIR / "main.py"), *args]


def slot_command_string(shortcut_spec: str) -> str:
    """The command a slot VBS runs (already quoted for WScript.Shell.Run)."""
    if IS_FROZEN:
        return f'""{sys.executable}"" --shortcut ""{shortcut_spec}""'
    pythonw = Path(sys.executable).parent / "pythonw.exe"
    resolver = BUNDLE_DIR / "resolver.py"
    return f'""{pythonw}"" ""{resolver}"" --shortcut ""{shortcut_spec}""'
