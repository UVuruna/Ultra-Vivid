"""Ultra Vivid daemon — global hotkeys + optional Chroma keyboard session.

Resident process started at log on (Task Scheduler, windowless pythonw):

- Registers a global hotkey (RegisterHotKey) for every binding in every
  non-hypershift shortcut set; pressing one applies its color preset.
  Hypershift sets are Synapse's job via the stable slot files.
- When the Chroma module is enabled, holds the Chroma session (heartbeat
  thread) and colors the Razer keyboard: following the schedule
  (followSchedule) and/or on every hotkey press.
- Reloads config automatically when config.json changes (mtime check).
- Exits immediately when there is nothing to do; single-instance via a
  named mutex.
"""

import ctypes
import ctypes.wintypes
import logging
import logging.handlers
import sys
import threading
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))

from core import apply as rgb
from core import chroma, schedule
from core import settings as settings_mod
from core.keymap import MOD_NOREPEAT, MODIFIER_FLAGS, VIRTUAL_KEYS

CONFIG_PATH = PROJECT_DIR / "config.json"
LOG_DIR = PROJECT_DIR / "logs"
MUTEX_NAME = "UltraVivid-Daemon"
SCHEDULE_POLL_SECONDS = 60.0
WM_HOTKEY = 0x0312

logger = logging.getLogger("daemon")
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


def _setup_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "daemon.log", maxBytes=512 * 1024, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()])


def _single_instance() -> bool:
    kernel32.CreateMutexW(None, False, MUTEX_NAME)
    ERROR_ALREADY_EXISTS = 183
    return kernel32.GetLastError() != ERROR_ALREADY_EXISTS


class Daemon:
    def __init__(self):
        self.cfg = settings_mod.load(CONFIG_PATH)
        self.cfg_mtime = CONFIG_PATH.stat().st_mtime
        self.hotkey_actions: dict[int, str] = {}   # hotkey id -> preset name
        self.chroma_session: chroma.ChromaSession | None = None
        self.stop_event = threading.Event()

    # -- config ------------------------------------------------------------

    def reload_if_changed(self) -> None:
        mtime = CONFIG_PATH.stat().st_mtime
        if mtime == self.cfg_mtime:
            return
        logger.info("config.json changed — reloading.")
        try:
            self.cfg = settings_mod.load(CONFIG_PATH)
            self.cfg_mtime = mtime
            self.register_hotkeys()
        except settings_mod.ConfigError as e:
            logger.error("Reload rejected, keeping previous config: %s", e)

    # -- hotkeys -----------------------------------------------------------

    def register_hotkeys(self) -> None:
        for hotkey_id in self.hotkey_actions:
            user32.UnregisterHotKey(None, hotkey_id)
        self.hotkey_actions.clear()
        if not self.cfg.shortcuts_enabled:
            logger.info("Shortcuts disabled in config — no hotkeys registered.")
            return
        next_id = 1
        for shortcut_set in self.cfg.shortcut_sets:
            flags = MODIFIER_FLAGS.get(shortcut_set.selector)
            if flags is None:      # hypershift: Synapse territory
                continue
            for key, preset in shortcut_set.bindings.items():
                vk = VIRTUAL_KEYS[key]
                if user32.RegisterHotKey(None, next_id, flags | MOD_NOREPEAT, vk):
                    self.hotkey_actions[next_id] = preset
                else:
                    logger.warning("RegisterHotKey failed for %s+%s (in use?)",
                                   shortcut_set.selector, key)
                next_id += 1
        logger.info("Registered %d hotkeys.", len(self.hotkey_actions))

    def apply_preset(self, preset: str) -> None:
        try:
            rgb.apply_preset(self.cfg, preset)
        except Exception:
            logger.exception("OpenRGB apply failed for %r", preset)
        self.push_chroma(preset)

    # -- chroma ------------------------------------------------------------

    def push_chroma(self, preset: str | None) -> None:
        if self.chroma_session is None:
            return
        hex_color = self.cfg.color_presets[preset][0] if preset else "000000"
        try:
            self.chroma_session.set_keyboard_color(hex_color)
        except chroma.ChromaError:
            logger.exception("Chroma push failed — dropping session.")
            self.chroma_session = None

    def chroma_thread(self) -> None:
        """Holds the session alive and optionally follows the schedule."""
        last_preset: str | None = ...  # sentinel: force first push
        while not self.stop_event.wait(chroma.HEARTBEAT_SECONDS):
            if not self.cfg.chroma.enabled:
                if self.chroma_session is not None:
                    self.chroma_session.close()
                    self.chroma_session = None
                continue
            try:
                if self.chroma_session is None:
                    self.chroma_session = chroma.ChromaSession()
                    last_preset = ...
                self.chroma_session.heartbeat()
                if self.cfg.chroma.follow_schedule:
                    now = datetime.now(schedule.tick_timezone(self.cfg))
                    preset = schedule.resolve(self.cfg, now)
                    if preset != last_preset:
                        self.push_chroma(preset)
                        last_preset = preset
            except chroma.ChromaError as e:
                # Documented fallback: Chroma endpoint may be absent (no
                # Synapse). Log, retry on the next beat — never crash.
                logger.warning("Chroma unavailable: %s", e)
                self.chroma_session = None

    # -- main loop ---------------------------------------------------------

    def run(self) -> None:
        needs_hotkeys = self.cfg.shortcuts_enabled and any(
            s.selector in MODIFIER_FLAGS for s in self.cfg.shortcut_sets)
        if not needs_hotkeys and not self.cfg.chroma.enabled:
            logger.info("Nothing to do (no daemon hotkeys, Chroma off) — exiting.")
            return

        self.register_hotkeys()
        chroma_worker = threading.Thread(target=self.chroma_thread, daemon=True)
        chroma_worker.start()

        logger.info("Daemon running.")
        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                self.reload_if_changed()
                preset = self.hotkey_actions.get(msg.wParam)
                if preset:
                    logger.info("Hotkey %d -> %r", msg.wParam, preset)
                    threading.Thread(
                        target=self.apply_preset, args=(preset,), daemon=True).start()
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        self.stop_event.set()


def main() -> None:
    _setup_logging()
    if not _single_instance():
        logger.info("Another daemon instance is running — exiting.")
        return
    Daemon().run()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Daemon crashed")
        raise
