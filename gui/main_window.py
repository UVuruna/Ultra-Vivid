"""Ultra Vivid main window — tabs, action bar, live status.

The tabs edit the raw config dict in place; Save validates and writes
(an invalid edit never reaches disk), Apply runs the resolver detached.
Opens portrait (W:H = 1:2, clamped to the screen) with a minimum width.
"""

import os
import subprocess
import tempfile
import threading
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QTabWidget,
    QVBoxLayout, QWidget,
)

from core import apply as rgb
from core import paths, schedule
from core import settings as settings_mod
from core import updates
from core.settings import ConfigError
from gui import config_io, theme
from gui.colors_tab import ColorsTab
from gui.devices_tab import DevicesTab
from gui.presets_tab import PresetsTab
from gui.shortcuts_tab import ShortcutsTab

ICO_PATH = paths.ASSETS_DIR / "UltraVivid.ico"
STATUS_REFRESH_MS = 30_000
MIN_WIDTH = 900               # owner spec: the shown width is the minimum
MIN_HEIGHT = 700
HEIGHT_SCREEN_FRACTION = 2    # owner spec: window height = screen height / 2


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ultra Vivid")
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
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

        # Update banner (hidden until a newer GitHub release is found).
        self.update_btn = QPushButton()
        self.update_btn.setProperty("update", True)
        self.update_btn.clicked.connect(self._install_update)
        self.update_btn.hide()
        self._update = None
        self._update_state = None       # None|found|downloading|ready|failed|launched
        self._update_path = None

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
        for b in (self.update_btn, task_btn, apply_btn, save_btn):
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

        # Monorepo standard: check GitHub for a newer release, offer an
        # update. Network work on a worker thread; the UI thread reads the
        # result off a light timer (Qt widgets are touched only here).
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._refresh_update_button)
        self._update_timer.start(1500)
        threading.Thread(target=self._check_updates, daemon=True).start()

    def _size_to_portrait(self) -> None:
        """Owner spec: NEVER full height — the window opens at HALF the
        screen height (1:2 of the screen), min width 900."""
        screen = QGuiApplication.primaryScreen()
        height = MIN_HEIGHT
        if screen is not None:
            height = max(MIN_HEIGHT,
                         screen.availableGeometry().height() // HEIGHT_SCREEN_FRACTION)
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
        result = subprocess.run(
            paths.launcher_command("--force"),
            capture_output=True, text=True, timeout=90, **paths.no_window())
        if result.returncode == 0:
            self.statusBar().showMessage("Applied.", 4000)
        else:
            QMessageBox.warning(self, "Ultra Vivid",
                                f"Apply failed:\n{(result.stderr or result.stdout).strip()}")

    def _install_tasks(self) -> None:
        if not self._save():
            return
        # --install-tasks re-launches itself elevated (UAC) and registers
        # the resolver + daemon tasks pointing at THIS program.
        subprocess.Popen(paths.launcher_command("--install-tasks"), **paths.no_window())

    # -- updates -----------------------------------------------------------

    def _check_updates(self) -> None:
        """Worker: one GitHub check per start. Only sets the attribute — the
        update timer shows the button on the UI thread."""
        try:
            cfg = settings_mod.parse(self.raw)
            self._update = updates.check(cfg.updates.repo, cfg.updates.check)
        except Exception:
            self._update = None
        if self._update:
            self._update_state = "found"

    def _install_update(self) -> None:
        upd = self._update
        if not upd or self._update_state not in ("found", "failed"):
            return
        if not upd.installer_url:
            webbrowser.open(upd.page_url)   # release without an exe asset
            return
        self._update_state = "downloading"
        self._refresh_update_button()
        threading.Thread(target=self._download_update, args=(upd,), daemon=True).start()

    def _download_update(self, upd) -> None:
        """Worker: fetch the installer to %TEMP%; the timer launches it."""
        try:
            path = Path(tempfile.gettempdir()) / f"UltraVivid_Setup_v{upd.version}.exe"
            with urllib.request.urlopen(upd.installer_url, timeout=30) as response, \
                    open(path, "wb") as out:
                while chunk := response.read(256 * 1024):
                    out.write(chunk)
        except Exception:
            self._update_state = "failed"
            return
        self._update_path = path
        self._update_state = "ready"

    def _refresh_update_button(self) -> None:
        state = self._update_state
        if state in (None, "launched") or self._update is None:
            return
        if state == "ready":
            # os.startfile = ShellExecute → the UAC prompt the installer's
            # admin manifest needs; then quit so files aren't in use.
            try:
                os.startfile(str(self._update_path))
            except OSError:
                self._update_state = "failed"
                self.update_btn.setText("Update failed — retry")
                self.update_btn.setEnabled(True)
                return
            self._update_state = "launched"
            self.close()
            return
        if state == "found":
            self.update_btn.setText(f"⬆️ Update to v{self._update.version}")
            self.update_btn.setEnabled(True)
        elif state == "downloading":
            self.update_btn.setText("Downloading update…")
            self.update_btn.setEnabled(False)
        elif state == "failed":
            self.update_btn.setText("Update failed — retry")
            self.update_btn.setEnabled(True)
        self.update_btn.show()
        self.statusBar().showMessage("Task installer launched (UAC).", 6000)
