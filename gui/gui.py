# gui.py - Auto OpenRGB GUI
# Entry point: python -m gui.gui  (from project root)

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QLabel, QLineEdit, QSpinBox, QComboBox, QPushButton,
    QHBoxLayout, QVBoxLayout, QGridLayout,
    QFileDialog, QMessageBox,
)

from gui.profile_scanner import scan_profiles
from gui.config_writer import read_config, write_config
from gui.runner import run_setup

# Project root = parent of gui/ folder
SCRIPT_DIR = Path(__file__).parent.parent
CONFIG_PATH = SCRIPT_DIR / "config.json"
ICO_PATH = SCRIPT_DIR / "assets" / "AutoOpenRGB.ico"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto OpenRGB Setup")
        self.resize(620, 480)

        if ICO_PATH.exists():
            self.setWindowIcon(QIcon(str(ICO_PATH)))

        self.profiles: list[str] = []
        self.schedule_rows: list[dict] = []  # {"start_edit", "end_lbl", "profile_combo"}
        self.fkey_combos: list[QComboBox] = []  # 12 items, F1-F12
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
        self.tabs.addTab(self.tab_schedule, "Raspored")
        self.tabs.addTab(self.tab_fkeys,    "Tastature")
        self.tabs.addTab(self.tab_extras,   "Ekstra")

        self._build_setup_tab()
        self._build_schedule_tab()
        self._build_fkeys_tab()
        self._build_extras_tab()
        self._build_bottom_bar()

    def _build_setup_tab(self):
        layout = QVBoxLayout(self.tab_setup)
        layout.setContentsMargins(10, 15, 10, 10)

        layout.addWidget(QLabel("OpenRGB putanja:"))

        path_row = QHBoxLayout()
        self.edit_path = QLineEdit()
        path_row.addWidget(self.edit_path)
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_openrgb)
        path_row.addWidget(btn_browse)
        layout.addLayout(path_row)

        self.lbl_status = QLabel("Status: -")
        layout.addWidget(self.lbl_status)

        layout.addSpacing(10)
        layout.addWidget(QLabel("Pronadjeni profili:"))

        self.lbl_profiles = QLabel("(nema)")
        self.lbl_profiles.setWordWrap(True)
        layout.addWidget(self.lbl_profiles)

        btn_rescan = QPushButton("Reskenuj profile")
        btn_rescan.clicked.connect(self._rescan)
        layout.addWidget(btn_rescan, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch()

    def _build_schedule_tab(self):
        layout = QVBoxLayout(self.tab_schedule)
        layout.setContentsMargins(10, 10, 10, 10)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Pocetni sat:"))
        self.spin_start_hour = QSpinBox()
        self.spin_start_hour.setRange(0, 23)
        self.spin_start_hour.setValue(3)
        self.spin_start_hour.setFixedWidth(55)
        ctrl.addWidget(self.spin_start_hour)

        ctrl.addSpacing(15)
        ctrl.addWidget(QLabel("Broj slotova:"))
        self.spin_slot_count = QSpinBox()
        self.spin_slot_count.setRange(2, 24)
        self.spin_slot_count.setValue(8)
        self.spin_slot_count.setFixedWidth(55)
        self.spin_slot_count.valueChanged.connect(lambda _: self._rebuild_schedule_table())
        ctrl.addWidget(self.spin_slot_count)

        btn_reset = QPushButton("Resetuj")
        btn_reset.clicked.connect(self._reset_schedule)
        ctrl.addWidget(btn_reset)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        # Column header
        hdr = QHBoxLayout()
        for text, w in [("Slot", 40), ("Pocetak", 70), ("Kraj", 70), ("Profil", 180)]:
            lbl = QLabel(text)
            lbl.setFixedWidth(w)
            hdr.addWidget(lbl)
        hdr.addStretch()
        layout.addLayout(hdr)

        self.schedule_container = QWidget()
        self.schedule_layout = QVBoxLayout(self.schedule_container)
        self.schedule_layout.setContentsMargins(0, 0, 0, 0)
        self.schedule_layout.setSpacing(2)
        layout.addWidget(self.schedule_container)

        self.lbl_gap_warning = QLabel("")
        self.lbl_gap_warning.setStyleSheet("color: orange;")
        layout.addWidget(self.lbl_gap_warning)

        layout.addStretch()
        self._rebuild_schedule_table()

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
        layout.addWidget(QLabel("Dodeli profil na F tastere:"))

        grid = QGridLayout()
        grid.setSpacing(8)
        self.fkey_combos = []

        for i in range(12):
            row, col = divmod(i, 2)
            lbl = QLabel(f"F{i + 1}:")
            lbl.setFixedWidth(35)
            combo = QComboBox()
            combo.addItems(self.profiles)
            combo.setFixedWidth(180)
            self.fkey_combos.append(combo)
            grid.addWidget(lbl,   row, col * 2)
            grid.addWidget(combo, row, col * 2 + 1)

        layout.addLayout(grid)
        info = QLabel("VBS fajlovi se generisu u rainbow/")
        info.setStyleSheet("color: gray;")
        layout.addWidget(info)
        layout.addStretch()

    def _build_extras_tab(self):
        layout = QVBoxLayout(self.tab_extras)
        layout.setContentsMargins(10, 15, 10, 10)
        layout.addWidget(QLabel("Rucni profili (pozivaju se VBS-om):"))

        self.extras_container = QWidget()
        self.extras_layout = QVBoxLayout(self.extras_container)
        self.extras_layout.setContentsMargins(0, 0, 0, 0)
        self.extras_layout.setSpacing(4)
        layout.addWidget(self.extras_container)

        btn_add = QPushButton("+ Dodaj novi")
        btn_add.clicked.connect(lambda: self._add_extra_row())
        layout.addWidget(btn_add, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch()

    def _add_extra_row(self, name: str = "", profile: str = "") -> None:
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)

        row_layout.addWidget(QLabel("Naziv:"))
        name_edit = QLineEdit(name)
        name_edit.setFixedWidth(100)
        row_layout.addWidget(name_edit)

        row_layout.addWidget(QLabel("Profil:"))
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

        self.lbl_bottom_status = QLabel("Spreman.")
        bar_layout.addWidget(self.lbl_bottom_status)
        bar_layout.addStretch()

        btn_apply = QPushButton("Primeni")
        btn_apply.clicked.connect(self._apply)
        bar_layout.addWidget(btn_apply)

        self._main_layout.addWidget(bar)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _browse_openrgb(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Izaberi OpenRGB.exe",
            "",
            "OpenRGB executable (OpenRGB.exe);;All files (*.*)",
        )
        if path:
            self.edit_path.setText(path.replace("/", "\\"))
            self._rescan()

    def _rescan(self):
        path = self.edit_path.text().strip()
        if not os.path.isfile(path):
            self.lbl_status.setText("Status: Fajl nije pronadjen")
            self.profiles = []
            self.lbl_profiles.setText("(nema)")
            return

        self.profiles = scan_profiles(path)
        if self.profiles:
            self.lbl_status.setText(f"Status: OpenRGB pronadjen - {len(self.profiles)} profila")
            self.lbl_profiles.setText(", ".join(self.profiles))
        else:
            self.lbl_status.setText("Status: OpenRGB nadjen, ali nema .orp profila")
            self.lbl_profiles.setText("(nema)")
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
        if not state:
            return
        self.edit_path.setText(state["openRGBPath"])
        self._rescan()
        if state.get("schedules"):
            self.spin_slot_count.setValue(len(state["schedules"]))
            self._rebuild_schedule_table()
            for i, item in enumerate(state["schedules"]):
                if i < len(self.schedule_rows):
                    self.schedule_rows[i]["start_edit"].setText(item["startTime"])
                    profile = item["profile"]
                    if profile in self.profiles:
                        self.schedule_rows[i]["profile_combo"].setCurrentText(profile)
            self._update_end_times()
        if state.get("rainbow"):
            for i, item in enumerate(state["rainbow"]):
                if i < len(self.fkey_combos):
                    profile = item["profile"]
                    if profile in self.profiles:
                        self.fkey_combos[i].setCurrentText(profile)
        for item in state.get("extras", []):
            self._add_extra_row(name=item.get("vbsName", ""), profile=item.get("profile", ""))

    def _apply(self):
        if not os.path.isfile(self.edit_path.text().strip()):
            QMessageBox.critical(self, "Greska", "OpenRGB putanja nije validna.")
            return
        self.lbl_bottom_status.setText("Pisanje config.json...")
        QApplication.processEvents()

        state = self._collect_state()
        write_config(str(CONFIG_PATH), state)

        self.lbl_bottom_status.setText("Pokretanje setup.ps1 (Admin)...")
        QApplication.processEvents()

        ok, msg = run_setup(str(SCRIPT_DIR))
        if ok:
            self.lbl_bottom_status.setText(f"OK - {msg}")
        else:
            self.lbl_bottom_status.setText(f"Greska - {msg}")

    def _collect_state(self) -> dict:
        """Collect current GUI state into dict for config_writer."""
        schedules = [
            {
                "taskName": f"OpenRGB slot{i + 1}",
                "vbsName": f"slot{i + 1}",
                "profile": row["profile_combo"].currentText(),
                "startTime": row["start_edit"].text(),
            }
            for i, row in enumerate(self.schedule_rows)
        ]
        rainbow = [
            {"vbsName": f"F{i + 1}", "profile": combo.currentText()}
            for i, combo in enumerate(self.fkey_combos)
        ]
        extras = [
            {"vbsName": row["name_edit"].text(), "profile": row["profile_combo"].currentText()}
            for row in self.extra_rows
            if row["name_edit"].text().strip()
        ]
        return {
            "openRGBPath": self.edit_path.text().strip(),
            "schedules": schedules,
            "extras": extras,
            "rainbow": rainbow,
        }


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
