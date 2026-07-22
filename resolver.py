"""Ultra Vivid resolver — the one entry point that puts color on the RGB.

Invocations:
    pythonw resolver.py                     scheduled tick: compute the active
                                            preset from the schedule and apply it
    python  resolver.py --dry-run           print the decision, touch nothing
    python  resolver.py --preset NAME       apply a named color preset directly
    python  resolver.py --shortcut "SetName:key"
                                            apply the preset that set binds to that
                                            key — the target of the per-set slot
                                            files; a stale slot is a quiet no-op
    python  resolver.py --list-devices      show devices as the server reports them
    python  resolver.py --off               all selected devices off
    python  resolver.py --write-slots       (re)generate shortcuts/slot-*.vbs —
                                            the files Synapse LAUNCH bindings
                                            point at; their paths never change,
                                            what a slot does lives in config

A tick re-applies only when the decision changed since the last run
(state file), so a frequent Task Scheduler tick costs nothing; --preset,
--shortcut, --off and --force always apply.
"""

import argparse
import json
import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))

from core import apply as rgb
from core import schedule, settings as settings_mod

CONFIG_PATH = PROJECT_DIR / "config.json"
LOG_DIR = PROJECT_DIR / "logs"
STATE_PATH = LOG_DIR / "state.json"
SLOTS_DIR = PROJECT_DIR / "shortcuts"

LOG_MAX_BYTES = 512 * 1024
LOG_BACKUPS = 3

logger = logging.getLogger("resolver")


def _setup_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "resolver.log", maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUPS, encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()])


def _read_state() -> dict:
    if STATE_PATH.is_file():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("state.json unreadable — treating as first run")
    return {}


def _write_state(preset: str | None) -> None:
    STATE_PATH.write_text(
        json.dumps({"lastPreset": preset, "at": datetime.now().isoformat()}),
        encoding="utf-8",
    )


def _shortcut_preset(cfg, spec: str) -> str | None:
    """Resolve 'SetName:key' (e.g. 'DUGA:q') to a preset name.

    Returns None when the set or key no longer exists — a stale slot
    file is a quiet no-op, never an error dialog on a keypress.
    """
    set_name, _, key = spec.partition(":")
    for shortcut_set in cfg.shortcut_sets:
        if shortcut_set.name.lower() == set_name.lower():
            preset = shortcut_set.bindings.get(key)
            if preset is None:
                logger.info("Slot %s: key not bound — nothing to do.", spec)
            return preset
    logger.info("Slot %s: set not found — nothing to do.", spec)
    return None


# filesystem-safe filename tokens for key labels
_KEY_FILE_TOKENS = {
    "-": "minus", "=": "equals", "[": "lbracket", "]": "rbracket",
    ";": "semicolon", "'": "quote", ",": "comma", ".": "dot",
    "/": "slash", "`": "backtick",
    "num.": "num-dot", "num+": "num-plus", "num-": "num-minus",
    "num*": "num-star", "num/": "num-slash",
}


def _safe_folder(name: str) -> str:
    return "".join(c for c in name if c not in '<>:"/\\|?*').strip() or "set"


def write_set_folder(cfg, shortcut_set) -> Path:
    """Create/refresh shortcuts/<SetName>/ with one VBS per chosen key.

    Every set gets its folder (the files activate the RGB standalone);
    for hypershift sets these are the files the user links in Synapse —
    existing files never change content-meaningfully, so a link is
    forever. Returns the folder path."""
    pythonw = Path(sys.executable).parent / "pythonw.exe"
    folder = SLOTS_DIR / _safe_folder(shortcut_set.name)
    folder.mkdir(parents=True, exist_ok=True)
    expected = set()
    for key in shortcut_set.bindings:
        file_name = f"{_KEY_FILE_TOKENS.get(key, key)}.vbs"
        expected.add(file_name)
        (folder / file_name).write_text(
            f"' Ultra Vivid shortcut slot: set {shortcut_set.name!r}, key {key!r}.\n"
            "' Bind Synapse LAUNCH to this file - the color it applies\n"
            "' is defined in config.json, never here.\n"
            'Set WshShell = CreateObject("WScript.Shell")\n'
            f'WshShell.Run """{pythonw}"" ""{PROJECT_DIR / "resolver.py"}""'
            f' --shortcut ""{shortcut_set.name}:{key}""", 0\n'
            "WScript.Quit\n",
            encoding="ascii",
        )
    for stale in folder.glob("*.vbs"):
        if stale.name not in expected:
            stale.unlink()
            logger.info("Removed stale slot: %s", stale)
    return folder


def _write_slots(cfg) -> None:
    """Refresh every set's folder and remove folders of deleted sets."""
    SLOTS_DIR.mkdir(exist_ok=True)
    for old_flat in SLOTS_DIR.glob("slot-*.vbs"):
        old_flat.unlink()  # pre-folder layout leftovers
    expected_folders = set()
    for shortcut_set in cfg.shortcut_sets:
        folder = write_set_folder(cfg, shortcut_set)
        expected_folders.add(folder.name)
        print(f"{shortcut_set.name}: {len(shortcut_set.bindings)} slots -> {folder}")
    for entry in SLOTS_DIR.iterdir():
        if entry.is_dir() and entry.name not in expected_folders:
            for f in entry.glob("*.vbs"):
                f.unlink()
            try:
                entry.rmdir()
                logger.info("Removed folder of deleted set: %s", entry.name)
            except OSError:
                logger.warning("Could not remove %s (extra files inside)", entry)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--preset")
    parser.add_argument("--shortcut", metavar="SET:KEY")
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--off", action="store_true")
    parser.add_argument("--force", action="store_true",
                        help="apply even if the decision has not changed")
    parser.add_argument("--write-slots", action="store_true")
    args = parser.parse_args()

    _setup_logging()
    cfg = settings_mod.load(CONFIG_PATH)

    if args.write_slots:
        _write_slots(cfg)
        return

    if args.list_devices:
        client = rgb.connect(cfg)
        try:
            for d in client.devices:
                print(f"[{d.id}] {d.name} ({d.type.name}, {len(d.leds)} LEDs)")
        finally:
            client.disconnect()
        return

    if args.off:
        rgb.apply_preset(cfg, None)
        _write_state(None)
        return

    if args.preset or args.shortcut:
        if args.preset:
            preset = args.preset
            if preset not in cfg.color_presets:
                raise SystemExit(f"unknown color preset {preset!r}")
        else:
            preset = _shortcut_preset(cfg, args.shortcut)
            if preset is None:
                return  # unbound slot: documented no-op
        rgb.apply_preset(cfg, preset)
        _write_state(preset)
        return

    # Scheduled tick
    now = datetime.now(schedule.tick_timezone(cfg))
    preset = schedule.resolve(cfg, now)
    logger.info("Tick %s -> preset %r", now.isoformat(timespec="seconds"), preset)
    if args.dry_run:
        print(f"now={now.isoformat(timespec='seconds')} -> preset={preset!r} "
              f"(colors={cfg.color_presets.get(preset) if preset else 'OFF'})")
        return
    state = _read_state()
    if not args.force and "lastPreset" in state and state["lastPreset"] == preset:
        logger.info("Unchanged since last tick — skipping apply.")
        return
    rgb.apply_preset(cfg, preset)
    _write_state(preset)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Resolver failed")
        raise
