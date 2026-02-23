# gui.py - Auto OpenRGB GUI
# Entry point: python -m gui.gui  (from project root)

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QLabel, QLineEdit, QSpinBox, QComboBox, QPushButton, QCheckBox,
    QHBoxLayout, QVBoxLayout, QGridLayout, QListWidget,
    QFileDialog, QMessageBox,
)

from gui.profile_scanner import scan_profiles
from gui.config_writer import read_config, write_config
from gui.runner import run_setup

# Project root and asset paths — handle PyInstaller frozen bundle
if getattr(sys, 'frozen', False):
    SCRIPT_DIR = Path(sys.executable).parent
    _ASSETS_BASE = Path(sys._MEIPASS)
else:
    SCRIPT_DIR = Path(__file__).parent.parent
    _ASSETS_BASE = SCRIPT_DIR

CONFIG_PATH = SCRIPT_DIR / "config.json"
ICO_PATH = _ASSETS_BASE / "assets" / "AutoOpenRGB.ico"

# Standard OpenRGB install locations checked on startup
_OPENRGB_CANDIDATES = [
    Path(r"C:\Program Files\OpenRGB\OpenRGB.exe"),
    Path(r"C:\Program Files (x86)\OpenRGB\OpenRGB.exe"),
]

# Key row definitions: (display option, keyRow value, 12 labels, 12 VK names for info)
_KEY_ROWS = [
    ("F1-F12", "F",
     ["F1","F2","F3","F4","F5","F6","F7","F8","F9","F10","F11","F12"]),
    ("Number row  (1-=)", "num",
     ["1","2","3","4","5","6","7","8","9","0","-","="]),
]

_MODIFIERS = ["Shift", "Ctrl+Shift", "Alt+Shift"]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto OpenRGB Setup")
        self.resize(640, 540)

        if ICO_PATH.exists():
            self.setWindowIcon(QIcon(str(ICO_PATH)))

        self.profiles: list[str] = []
        self.schedule_rows: list[dict] = []  # {"start_edit", "end_lbl", "profile_combo"}
        self.fkey_combos: list[QComboBox] = []   # 12 items
        self.fkey_labels: list[QLabel] = []       # 12 items — updated when key row changes
        self.extra_rows: list[dict] = []  # {"name_edit", "profile_combo", "widget"}

        self._build_ui()
        self._load_existing_config()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        self._main_layout = QVBoxLayout(central)
        self._main_layout.setContentsMargins(10, 10, 10, 0)

        self.tabs = QTabWidget()
        self._main_layout.addWidget(self.tabs)

        self.tab_setup    = QWidget()
        self.tab_schedule = QWidget()
        self.tab_fkeys    = QWidget()
        self.tab_extras   = QWidget()

        self.tabs.addTab(self.tab_setup,    "Setup")
        self.tabs.addTab(self.tab_schedule, "Schedule")
        self.tabs.addTab(self.tab_fkeys,    "Keyboard")
        self.tabs.addTab(self.tab_extras,   "Extras")

        self._build_setup_tab()
        self._build_schedule_tab()
        self._build_fkeys_tab()
        self._build_extras_tab()
        self._build_bottom_bar()

    def _build_setup_tab(self):
        layout = QVBoxLayout(self.tab_setup)
        layout.setContentsMargins(10, 15, 10, 10)

        layout.addWidget(QLabel("OpenRGB path:"))

        path_row = QHBoxLayout()
        self.edit_path = QLineEdit()
        path_row.addWidget(self.edit_path)
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_openrgb)
        path_row.addWidget(btn_browse)
        layout.addLayout(path_row)

        self.lbl_status = QLabel("Status: -")
        layout.addWidget(self.lbl_status)

        layout.addSpacing(8)
        layout.addWidget(QLabel("Found profiles:"))

        self.list_profiles = QListWidget()
        self.list_profiles.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.list_profiles.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.list_profiles, stretch=1)

        btn_rescan = QPushButton("Rescan profiles")
        btn_rescan.clicked.connect(self._rescan)
        layout.addWidget(btn_rescan, alignment=Qt.AlignmentFlag.AlignLeft)

    def _build_schedule_tab(self):
        layout = QVBoxLayout(self.tab_schedule)
        layout.setContentsMargins(10, 10, 10, 10)

        # Enable checkbox
        self.cb_schedule_enabled = QCheckBox("Enable time-based schedule")
        self.cb_schedule_enabled.setChecked(True)
        self.cb_schedule_enabled.toggled.connect(self._on_schedule_enabled_changed)
        layout.addWidget(self.cb_schedule_enabled)

        layout.addSpacing(6)

        # Schedule controls container (toggled by checkbox)
        self._schedule_body = QWidget()
        body_layout = QVBoxLayout(self._schedule_body)
        body_layout.setContentsMargins(0, 0, 0, 0)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Start hour:"))
        self.spin_start_hour = QSpinBox()
        self.spin_start_hour.setRange(0, 23)
        self.spin_start_hour.setValue(3)
        self.spin_start_hour.setFixedWidth(55)
        ctrl.addWidget(self.spin_start_hour)

        ctrl.addSpacing(15)
        ctrl.addWidget(QLabel("Slot count:"))
        self.spin_slot_count = QSpinBox()
        self.spin_slot_count.setRange(2, 24)
        self.spin_slot_count.setValue(8)
        self.spin_slot_count.setFixedWidth(55)
        self.spin_slot_count.valueChanged.connect(lambda _: self._rebuild_schedule_table())
        ctrl.addWidget(self.spin_slot_count)

        btn_reset = QPushButton("Reset")
        btn_reset.clicked.connect(self._reset_schedule)
        ctrl.addWidget(btn_reset)
        ctrl.addStretch()
        body_layout.addLayout(ctrl)

        # Column header
        hdr = QHBoxLayout()
        for text, w in [("Slot", 40), ("Start", 70), ("End", 70), ("Profile", 180)]:
            lbl = QLabel(text)
            lbl.setFixedWidth(w)
            hdr.addWidget(lbl)
        hdr.addStretch()
        body_layout.addLayout(hdr)

        self.schedule_container = QWidget()
        self.schedule_layout = QVBoxLayout(self.schedule_container)
        self.schedule_layout.setContentsMargins(0, 0, 0, 0)
        self.schedule_layout.setSpacing(2)
        body_layout.addWidget(self.schedule_container)

        self.lbl_gap_warning = QLabel("")
        self.lbl_gap_warning.setStyleSheet("color: orange;")
        body_layout.addWidget(self.lbl_gap_warning)

        body_layout.addStretch()
        layout.addWidget(self._schedule_body)

        self._rebuild_schedule_table()

    def _on_schedule_enabled_changed(self, enabled: bool):
        self._schedule_body.setEnabled(enabled)

    def _rebuild_schedule_table(self, keep_profiles: bool = False):
        """Rebuild schedule rows from current slot count and start hour."""
        old_profiles = [row["profile_combo"].currentText() for row in self.schedule_rows] if keep_profiles else []

        while self.schedule_layout.count():
            item = self.schedule_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.schedule_rows.clear()

        count = self.spin_slot_count.value()
        start = self.spin_start_hour.value()
        duration = 24 // count if count else 3

        for i in range(count):
            hour = (start + duration * i) % 24
            start_time = f"{hour:02d}:00"

            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)

            num_lbl = QLabel(str(i + 1))
            num_lbl.setFixedWidth(40)
            row_layout.addWidget(num_lbl)

            start_edit = QLineEdit(start_time)
            start_edit.setFixedWidth(60)
            start_edit.editingFinished.connect(self._update_end_times)
            row_layout.addWidget(start_edit)

            end_lbl = QLabel("-")
            end_lbl.setFixedWidth(60)
            row_layout.addWidget(end_lbl)

            combo = QComboBox()
            combo.addItems(self.profiles)
            combo.setFixedWidth(180)
            if i < len(old_profiles) and old_profiles[i] in self.profiles:
                combo.setCurrentText(old_profiles[i])
            row_layout.addWidget(combo)
            row_layout.addStretch()

            self.schedule_layout.addWidget(row_widget)
            self.schedule_rows.append({
                "start_edit": start_edit,
                "end_lbl": end_lbl,
                "profile_combo": combo,
            })

        self._update_end_times()

    def _update_end_times(self):
        """Recalculate end time labels."""
        rows = self.schedule_rows
        if not rows:
            return
        for i, row in enumerate(rows):
            next_start = rows[(i + 1) % len(rows)]["start_edit"].text()
            try:
                nh, nm = map(int, next_start.split(":"))
                end_min = (nh * 60 + nm - 1) % (24 * 60)
                row["end_lbl"].setText(f"{end_min // 60:02d}:{end_min % 60:02d}")
            except ValueError:
                row["end_lbl"].setText("??")
        self.lbl_gap_warning.setText("")

    def _reset_schedule(self):
        self._rebuild_schedule_table(keep_profiles=True)

    def _build_fkeys_tab(self):
        layout = QVBoxLayout(self.tab_fkeys)
        layout.setContentsMargins(10, 15, 10, 10)

        # Enable checkbox
        self.cb_shortcuts_enabled = QCheckBox("Enable keyboard shortcuts")
        self.cb_shortcuts_enabled.setChecked(True)
        self.cb_shortcuts_enabled.toggled.connect(self._on_shortcuts_enabled_changed)
        layout.addWidget(self.cb_shortcuts_enabled)

        layout.addSpacing(6)

        # Options body (toggled by checkbox)
        self._shortcuts_body = QWidget()
        body_layout = QVBoxLayout(self._shortcuts_body)
        body_layout.setContentsMargins(0, 0, 0, 0)

        # Modifier + key row selectors
        opts_row = QHBoxLayout()
        opts_row.addWidget(QLabel("Modifier:"))
        self.combo_modifier = QComboBox()
        self.combo_modifier.addItems(_MODIFIERS)
        self.combo_modifier.setFixedWidth(120)
        opts_row.addWidget(self.combo_modifier)

        opts_row.addSpacing(20)
        opts_row.addWidget(QLabel("Key row:"))
        self.combo_keyrow = QComboBox()
        for label, _, _ in _KEY_ROWS:
            self.combo_keyrow.addItem(label)
        self.combo_keyrow.setFixedWidth(160)
        self.combo_keyrow.currentIndexChanged.connect(self._on_keyrow_changed)
        opts_row.addWidget(self.combo_keyrow)
        opts_row.addStretch()
        body_layout.addLayout(opts_row)

        body_layout.addSpacing(8)

        # Grid of 12 key assignments
        grid = QGridLayout()
        grid.setSpacing(8)
        self.fkey_combos = []
        self.fkey_labels = []

        initial_labels = _KEY_ROWS[0][2]
        for i in range(12):
            row, col = divmod(i, 2)
            lbl = QLabel(f"{initial_labels[i]}:")
            lbl.setFixedWidth(35)
            combo = QComboBox()
            combo.addItems(self.profiles)
            combo.setFixedWidth(180)
            self.fkey_labels.append(lbl)
            self.fkey_combos.append(combo)
            grid.addWidget(lbl,   row, col * 2)
            grid.addWidget(combo, row, col * 2 + 1)

        body_layout.addLayout(grid)
        layout.addWidget(self._shortcuts_body)

        info = QLabel(
            "Hotkey daemon (hotkeys.ps1) is generated in rainbow/ and runs at login via Task Scheduler."
        )
        info.setStyleSheet("color: gray;")
        info.setWordWrap(True)
        layout.addWidget(info)
        layout.addStretch()

    def _on_shortcuts_enabled_changed(self, enabled: bool):
        self._shortcuts_body.setEnabled(enabled)

    def _on_keyrow_changed(self, index: int):
        """Update key labels in the grid when key row selection changes."""
        labels = _KEY_ROWS[index][2]
        for i, lbl in enumerate(self.fkey_labels):
            lbl.setText(f"{labels[i]}:")

    def _build_extras_tab(self):
        layout = QVBoxLayout(self.tab_extras)
        layout.setContentsMargins(10, 15, 10, 10)
        layout.addWidget(QLabel("Manual profiles (called via VBS shortcut):"))

        self.extras_container = QWidget()
        self.extras_layout = QVBoxLayout(self.extras_container)
        self.extras_layout.setContentsMargins(0, 0, 0, 0)
        self.extras_layout.setSpacing(4)
        layout.addWidget(self.extras_container)

        btn_add = QPushButton("+ Add new")
        btn_add.clicked.connect(lambda: self._add_extra_row())
        layout.addWidget(btn_add, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch()

    def _add_extra_row(self, name: str = "", profile: str = "") -> None:
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)

        row_layout.addWidget(QLabel("Name:"))
        name_edit = QLineEdit(name)
        name_edit.setFixedWidth(100)
        row_layout.addWidget(name_edit)

        row_layout.addWidget(QLabel("Profile:"))
        combo = QComboBox()
        combo.addItems(self.profiles)
        combo.setFixedWidth(180)
        if profile and profile in self.profiles:
            combo.setCurrentText(profile)
        row_layout.addWidget(combo)

        row = {"name_edit": name_edit, "profile_combo": combo, "widget": row_widget}

        btn_del = QPushButton("X")
        btn_del.setFixedWidth(30)
        btn_del.clicked.connect(lambda: self._delete_extra_row(row))
        row_layout.addWidget(btn_del)
        row_layout.addStretch()

        self.extras_layout.addWidget(row_widget)
        self.extra_rows.append(row)

    def _delete_extra_row(self, row: dict) -> None:
        if row in self.extra_rows:
            self.extra_rows.remove(row)
        row["widget"].deleteLater()

    def _build_bottom_bar(self):
        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 5, 0, 10)

        self.lbl_bottom_status = QLabel("Ready.")
        bar_layout.addWidget(self.lbl_bottom_status)
        bar_layout.addStretch()

        btn_apply = QPushButton("Apply")
        btn_apply.clicked.connect(self._apply)
        bar_layout.addWidget(btn_apply)

        self._main_layout.addWidget(bar)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _auto_detect_openrgb(self) -> str | None:
        """Check standard install locations for OpenRGB.exe."""
        for p in _OPENRGB_CANDIDATES:
            if p.exists():
                return str(p)
        return None

    def _browse_openrgb(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select OpenRGB.exe",
            "",
            "OpenRGB executable (OpenRGB.exe);;All files (*.*)",
        )
        if path:
            self.edit_path.setText(path.replace("/", "\\"))
            self._rescan()

    def _rescan(self):
        path = self.edit_path.text().strip()
        if not os.path.isfile(path):
            self.lbl_status.setText("Status: File not found")
            self.profiles = []
            self.list_profiles.clear()
            return

        self.profiles = scan_profiles(path)
        if self.profiles:
            self.lbl_status.setText(f"Status: OpenRGB found — {len(self.profiles)} profiles")
            self.list_profiles.clear()
            for p in self.profiles:
                self.list_profiles.addItem(p)
        else:
            self.lbl_status.setText("Status: OpenRGB found, but no .orp profiles")
            self.list_profiles.clear()
        self._refresh_dropdowns()

    def _refresh_dropdowns(self):
        """Update all dropdowns after profile rescan."""
        self._rebuild_schedule_table(keep_profiles=True)
        self._refresh_fkeys()
        self._refresh_extras()

    def _refresh_fkeys(self):
        """Update F-key combobox values after profile rescan."""
        for combo in self.fkey_combos:
            current = combo.currentText()
            combo.clear()
            combo.addItems(self.profiles)
            if current in self.profiles:
                combo.setCurrentText(current)

    def _refresh_extras(self):
        """Update extras combobox values after profile rescan."""
        for row in self.extra_rows:
            combo = row["profile_combo"]
            current = combo.currentText()
            combo.clear()
            combo.addItems(self.profiles)
            if current in self.profiles:
                combo.setCurrentText(current)

    def _load_existing_config(self):
        state = read_config(str(CONFIG_PATH))
        if state:
            self.edit_path.setText(state["openRGBPath"])
            self._rescan()

            # Schedule
            sched = state.get("schedules", {})
            self.cb_schedule_enabled.setChecked(sched.get("enabled", True))
            sched_items = sched.get("items", [])
            if sched_items:
                self.spin_slot_count.setValue(len(sched_items))
                self._rebuild_schedule_table()
                for i, item in enumerate(sched_items):
                    if i < len(self.schedule_rows):
                        self.schedule_rows[i]["start_edit"].setText(item["startTime"])
                        profile = item["profile"]
                        if profile in self.profiles:
                            self.schedule_rows[i]["profile_combo"].setCurrentText(profile)
                self._update_end_times()

            # Shortcuts
            shorts = state.get("shortcuts", {})
            self.cb_shortcuts_enabled.setChecked(shorts.get("enabled", True))
            modifier = shorts.get("modifier", "Shift")
            if modifier in _MODIFIERS:
                self.combo_modifier.setCurrentText(modifier)
            key_row = shorts.get("keyRow", "F")
            kr_index = next((i for i, (_, v, _) in enumerate(_KEY_ROWS) if v == key_row), 0)
            self.combo_keyrow.setCurrentIndex(kr_index)
            for i, item in enumerate(shorts.get("items", [])):
                if i < len(self.fkey_combos):
                    profile = item.get("profile", "")
                    if profile in self.profiles:
                        self.fkey_combos[i].setCurrentText(profile)

            for item in state.get("extras", []):
                self._add_extra_row(name=item.get("vbsName", ""), profile=item.get("profile", ""))
        else:
            # No config — try to auto-detect OpenRGB from standard install locations
            detected = self._auto_detect_openrgb()
            if detected:
                self.edit_path.setText(detected)
                self._rescan()

    def _apply(self):
        if not os.path.isfile(self.edit_path.text().strip()):
            QMessageBox.critical(self, "Error", "OpenRGB path is not valid.")
            return
        self.lbl_bottom_status.setText("Writing config.json...")
        QApplication.processEvents()

        state = self._collect_state()
        write_config(str(CONFIG_PATH), state)

        self.lbl_bottom_status.setText("Running setup.ps1 (Admin)...")
        QApplication.processEvents()

        ok, msg = run_setup(str(SCRIPT_DIR))
        if ok:
            self.lbl_bottom_status.setText(f"OK — {msg}")
        else:
            self.lbl_bottom_status.setText(f"Error — {msg}")

    def _collect_state(self) -> dict:
        """Collect current GUI state into dict for config_writer."""
        schedules_items = [
            {
                "taskName": f"OpenRGB slot{i + 1}",
                "vbsName": f"slot{i + 1}",
                "profile": row["profile_combo"].currentText(),
                "startTime": row["start_edit"].text(),
            }
            for i, row in enumerate(self.schedule_rows)
        ]

        kr_index = self.combo_keyrow.currentIndex()
        key_row_value = _KEY_ROWS[kr_index][1]
        key_row_labels = _KEY_ROWS[kr_index][2]

        shortcuts_items = [
            {"vbsName": key_row_labels[i], "profile": combo.currentText()}
            for i, combo in enumerate(self.fkey_combos)
        ]

        extras = [
            {"vbsName": row["name_edit"].text(), "profile": row["profile_combo"].currentText()}
            for row in self.extra_rows
            if row["name_edit"].text().strip()
        ]

        return {
            "openRGBPath": self.edit_path.text().strip(),
            "schedules": {
                "enabled": self.cb_schedule_enabled.isChecked(),
                "items": schedules_items,
            },
            "shortcuts": {
                "enabled": self.cb_shortcuts_enabled.isChecked(),
                "modifier": self.combo_modifier.currentText(),
                "keyRow": key_row_value,
                "items": shortcuts_items,
            },
            "extras": extras,
        }


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
