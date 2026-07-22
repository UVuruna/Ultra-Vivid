"""Shortcuts tab — shortcut SETS mapping keys to color presets.

Owner flow: ADD set → pick selector (shift / ctrl / ctrl+shift /
alt+shift / hypershift) → pick key row → bind keys to presets.

Standard selectors are served by the hotkey daemon; hypershift sets are
bound in Razer Synapse BY HAND ONCE to the stable shortcuts/slot-*.vbs
files ("Write slot files" regenerates them).
"""

import subprocess
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel, QListWidget,
    QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from core.keymap import KEY_ROWS
from core.settings import SHORTCUT_KEYSETS, SHORTCUT_SELECTORS
from gui import theme
from gui.schedule_tab import combo_value, preset_combo


class ShortcutsTab(QWidget):
    def __init__(self, raw: dict):
        super().__init__()
        self.raw = raw
        self._loading = False

        self.enabled = QCheckBox("Shortcuts enabled (hotkey daemon)")
        self.enabled.toggled.connect(
            lambda on: self.raw["shortcuts"].__setitem__("enabled", on))

        self.set_list = QListWidget()
        self.set_list.currentRowChanged.connect(lambda *_: self._load_set())
        add_set = QPushButton("＋ Add set")
        add_set.clicked.connect(self._add_set)
        remove_set = QPushButton("Remove set")
        remove_set.setProperty("secondary", True)
        remove_set.clicked.connect(self._remove_set)
        write_slots = QPushButton("Write slot files (Synapse)")
        write_slots.setProperty("secondary", True)
        write_slots.clicked.connect(self._write_slots)

        left = QVBoxLayout()
        left.addWidget(self.set_list, 1)
        for b in (add_set, remove_set, write_slots):
            left.addWidget(b)

        self.selector = QComboBox()
        self.selector.addItems(SHORTCUT_SELECTORS)
        self.selector.currentTextChanged.connect(self._store_set)
        self.keys = QComboBox()
        self.keys.addItems(SHORTCUT_KEYSETS)
        self.keys.currentTextChanged.connect(self._keys_changed)

        self.bindings_grid = QGridLayout()
        self.bindings_grid.setSpacing(theme.SPACE_S)
        self.binding_combos: dict[str, QComboBox] = {}
        bindings_host = QWidget()
        bindings_host.setLayout(self.bindings_grid)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(bindings_host)

        hint = QLabel("hypershift sets: bind each Synapse LAUNCH to its slot file ONCE —\n"
                      "re-mapping presets here is then a pure config change.\n"
                      "Other selectors are global hotkeys served by the daemon.")
        hint.setProperty("hint", True)

        form = QGridLayout()
        form.addWidget(QLabel("Selector"), 0, 0)
        form.addWidget(self.selector, 0, 1)
        form.addWidget(QLabel("Key row"), 0, 2)
        form.addWidget(self.keys, 0, 3)

        right = QVBoxLayout()
        right.addLayout(form)
        right.addWidget(scroll, 1)
        right.addWidget(hint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_M, theme.SPACE_M, theme.SPACE_M, theme.SPACE_M)
        layout.setSpacing(theme.SPACE_M)
        layout.addWidget(self.enabled)
        body = QHBoxLayout()
        body.addLayout(left, 1)
        body.addLayout(right, 2)
        layout.addLayout(body, 1)

        self.reload()

    # -- data --------------------------------------------------------------

    def _sets(self) -> list[dict]:
        return self.raw["shortcuts"]["sets"]

    def _current(self) -> dict | None:
        row = self.set_list.currentRow()
        return self._sets()[row] if 0 <= row < len(self._sets()) else None

    def reload(self) -> None:
        self.enabled.setChecked(bool(self.raw["shortcuts"].get("enabled", True)))
        row = max(self.set_list.currentRow(), 0)
        self.set_list.clear()
        for s in self._sets():
            self.set_list.addItem(f"{s['selector']}  ·  {s['keys']}")
        if self._sets():
            self.set_list.setCurrentRow(min(row, len(self._sets()) - 1))
        self._load_set()

    def _load_set(self) -> None:
        current = self._current()
        self._loading = True
        for w in (self.selector, self.keys):
            w.setEnabled(current is not None)
        if current:
            self.selector.setCurrentText(current["selector"])
            self.keys.setCurrentText(current["keys"])
        self._rebuild_bindings()
        self._loading = False

    def _rebuild_bindings(self) -> None:
        while self.bindings_grid.count():
            item = self.bindings_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.binding_combos.clear()
        current = self._current()
        if not current:
            return
        for i, key in enumerate(KEY_ROWS[current["keys"]]):
            combo = preset_combo(self.raw, current["bindings"].get(key), allow_none=True)
            combo.currentTextChanged.connect(self._store_bindings)
            self.binding_combos[key] = combo
            row, col = i % 6, (i // 6) * 2
            self.bindings_grid.addWidget(QLabel(key), row, col)
            self.bindings_grid.addWidget(combo, row, col + 1)
        self.bindings_grid.setRowStretch(6, 1)

    # -- actions -----------------------------------------------------------

    def _add_set(self) -> None:
        self._sets().append({"selector": "shift", "keys": "fkeys", "bindings": {}})
        self.reload()
        self.set_list.setCurrentRow(len(self._sets()) - 1)

    def _remove_set(self) -> None:
        row = self.set_list.currentRow()
        if row < 0:
            return
        del self._sets()[row]
        self.reload()

    def _store_set(self) -> None:
        current = self._current()
        if current is None or self._loading:
            return
        current["selector"] = self.selector.currentText()
        self.set_list.currentItem().setText(
            f"{current['selector']}  ·  {current['keys']}")

    def _keys_changed(self) -> None:
        current = self._current()
        if current is None or self._loading:
            return
        current["keys"] = self.keys.currentText()
        current["bindings"] = {}
        self._store_set()
        self._rebuild_bindings()

    def _store_bindings(self) -> None:
        current = self._current()
        if current is None or self._loading:
            return
        current["bindings"] = {
            key: value for key, combo in self.binding_combos.items()
            if (value := combo_value(combo)) is not None
        }

    def _write_slots(self) -> None:
        resolver = Path(__file__).parent.parent / "resolver.py"
        result = subprocess.run(
            [sys.executable, str(resolver), "--write-slots"],
            capture_output=True, text=True)
        if result.returncode == 0:
            QMessageBox.information(self, "Ultra Vivid", result.stdout.strip()
                                    or "Slot files written.")
        else:
            QMessageBox.warning(self, "Ultra Vivid",
                                f"Failed:\n{result.stderr.strip()}")
