"""Ultra Vivid main window — tabs, action bar, live status.

The tabs edit the raw config dict in place; Save validates and writes
(an invalid edit never reaches disk), Apply runs the resolver detached.
Opens portrait (W:H = 1:2, clamped to the screen) with a minimum width.
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QTabWidget,
    QVBoxLayout, QWidget,
)

from core import apply as rgb
from core import schedule
from core import settings as settings_mod
from core.settings import ConfigError
from gui import config_io, theme
from gui.colors_tab import ColorsTab
from gui.devices_tab import DevicesTab
from gui.presets_tab import PresetsTab
from gui.shortcuts_tab import ShortcutsTab

PROJECT_DIR = Path(__file__).parent.parent
ICO_PATH = PROJECT_DIR / "assets" / "UltraVivid.ico"
STATUS_REFRESH_MS = 30_000
MIN_WIDTH = 900               # owner spec: the shown width is the minimum
ASPECT_H_PER_W = 2            # owner spec: open at W:H = 1:2 (portrait)
SCREEN_MARGIN = 80


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ultra Vivid")
        self.setMinimumWidth(MIN_WIDTH)
        self._size_to_portrait()
        if ICO_PATH.exists():
            self.setWindowIcon(QIcon(str(ICO_PATH)))

        self.raw = config_io.load_raw()

        try:
            hypershift_available = rgb.detect_hypershift_keyboard(
                settings_mod.parse(self.raw))
        except ConfigError:
            hypershift_available = False

        self.colors_tab = ColorsTab(self.raw)
        self.presets_tab = PresetsTab(self.raw)
        self.devices_tab = DevicesTab(self.raw)
        self.shortcuts_tab = ShortcutsTab(self.raw, hypershift_available)
        self.colors_tab.colors_changed.connect(self.presets_tab.reload)
        self.colors_tab.colors_changed.connect(self.shortcuts_tab.reload)

        tabs = QTabWidget()
        tabs.addTab(self.colors_tab, "🎨 Colors")
        tabs.addTab(self.presets_tab, "🕑 Presets")
        tabs.addTab(self.devices_tab, "🖥 Devices")
        tabs.addTab(self.shortcuts_tab, "⌨ Shortcuts")

        self.now_label = QLabel()
        self.now_label.setProperty("hint", True)

        save_btn = QPushButton("💾 Save")
        save_btn.clicked.connect(self._save)
        apply_btn = QPushButton("▶ Apply now")
        apply_btn.setProperty("secondary", True)
        apply_btn.clicked.connect(self._apply_now)
        task_btn = QPushButton("⚙ Install tasks…")
        task_btn.setProperty("secondary", True)
        task_btn.clicked.connect(self._install_tasks)

        bar = QHBoxLayout()
        bar.addWidget(self.now_label, 1)
        for b in (task_btn, apply_btn, save_btn):
            bar.addWidget(b)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(theme.SPACE_M, theme.SPACE_M, theme.SPACE_M, theme.SPACE_M)
        layout.setSpacing(theme.SPACE_M)
        layout.addWidget(tabs, 1)
        layout.addLayout(bar)
        self.setCentralWidget(central)

        self._refresh_status()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_status)
        self._timer.start(STATUS_REFRESH_MS)

    def _size_to_portrait(self) -> None:
        """W:H = 1:2, clamped so the window always fits the screen."""
        screen = QGuiApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        height = MIN_WIDTH * ASPECT_H_PER_W
        if available is not None:
            height = min(height, available.height() - SCREEN_MARGIN)
        self.resize(MIN_WIDTH, height)

    # -- status ------------------------------------------------------------

    def _refresh_status(self) -> None:
        try:
            cfg = settings_mod.parse(self.raw)
            now = datetime.now(schedule.tick_timezone(cfg))
            color = schedule.resolve(cfg, now)
            active = cfg.active_preset or "no active preset"
            shown = color if color else "OFF (all RGB dark)"
            self.now_label.setText(f"Active preset: {active}  →  right now: {shown}")
        except ConfigError as e:
            self.now_label.setText(f"⚠ Config incomplete: {e}")
        except Exception as e:  # never let the status line kill the GUI
            self.now_label.setText(f"⚠ {e}")

    # -- actions -----------------------------------------------------------

    def _save(self) -> bool:
        try:
            config_io.save_raw(self.raw)
        except ConfigError as e:
            QMessageBox.warning(self, "Ultra Vivid", f"Not saved — fix this first:\n\n{e}")
            return False
        self.statusBar().showMessage("Saved.", 4000)
        self._refresh_status()
        return True

    def _apply_now(self) -> None:
        if not self._save():
            return
        resolver = PROJECT_DIR / "resolver.py"
        result = subprocess.run(
            [sys.executable, str(resolver), "--force"],
            capture_output=True, text=True, timeout=90)
        if result.returncode == 0:
            self.statusBar().showMessage("Applied.", 4000)
        else:
            QMessageBox.warning(self, "Ultra Vivid",
                                f"Apply failed:\n{(result.stderr or result.stdout).strip()}")

    def _install_tasks(self) -> None:
        if not self._save():
            return
        script = PROJECT_DIR / "install-task.ps1"
        subprocess.run([
            "powershell", "-NoProfile", "-Command",
            f'Start-Process powershell -ArgumentList '
            f'"-NoProfile -ExecutionPolicy Bypass -File `"{script}`"" -Verb RunAs'
        ])
        self.statusBar().showMessage("Task installer launched (UAC).", 6000)
