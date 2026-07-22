"""Ultra Vivid resolver — the one entry point that puts color on the RGB.

Invocations:
    pythonw resolver.py                     scheduled tick: compute the active
                                            preset from the schedule and apply it
    python  resolver.py --dry-run           print the decision, touch nothing
    python  resolver.py --preset NAME       apply a named color preset directly
    python  resolver.py --shortcut SET:KEY  apply the preset bound to a shortcut
                                            (SET = set index, KEY = key label) —
                                            the stable target for Synapse LAUNCH
                                            bindings and the hotkey daemon
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


def _shortcut_preset(cfg, spec: str) -> str:
    set_index_str, _, key = spec.partition(":")
    try:
        shortcut_set = cfg.shortcut_sets[int(set_index_str)]
    except (ValueError, IndexError):
        raise SystemExit(f"--shortcut: no shortcut set {set_index_str!r} in config")
    if key not in shortcut_set.bindings:
        raise SystemExit(f"--shortcut: key {key!r} not bound in set {set_index_str}")
    return shortcut_set.bindings[key]


def _write_slots(cfg) -> None:
    """Generate one stable VBS per shortcut binding. Synapse LAUNCH
    bindings point at these paths ONCE and never need re-binding: the
    slot only names (set, key) — the bound preset lives in config."""
    pythonw = Path(sys.executable).parent / "pythonw.exe"
    SLOTS_DIR.mkdir(exist_ok=True)
    count = 0
    for set_index, shortcut_set in enumerate(cfg.shortcut_sets):
        for key in shortcut_set.bindings:
            slot_path = SLOTS_DIR / f"slot-{set_index}-{key}.vbs"
            slot_path.write_text(
                "' Ultra Vivid stable shortcut slot - bind Synapse LAUNCH to this file.\n"
                "' What it applies is defined in config.json, never here.\n"
                'Set WshShell = CreateObject("WScript.Shell")\n'
                f'WshShell.Run """{pythonw}"" ""{PROJECT_DIR / "resolver.py"}""'
                f' --shortcut {set_index}:{key}", 0\n'
                "WScript.Quit\n",
                encoding="ascii",
            )
            count += 1
    print(f"Wrote {count} slot files to {SLOTS_DIR}")


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
        preset = args.preset or _shortcut_preset(cfg, args.shortcut)
        if preset not in cfg.color_presets:
            raise SystemExit(f"unknown color preset {preset!r}")
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
