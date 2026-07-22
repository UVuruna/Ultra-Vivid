"""Shortcuts tab — the owner's flow, exactly:

1. ADD a named set (e.g. "DUGA")
2. pick the selector (shift / ctrl / alt / combos / Razer Hypershift —
   hypershift is offered only when a capable keyboard was detected)
3. pick ANY keys (letters, number row, numpad, F-keys — free mix)
4. pick a color for each key
5. "Create shortcut files" builds shortcuts/<SetName>/<key>.vbs
6. a. normal selector → the daemon registers the hotkeys itself
   b. hypershift → the folder opens, Razer Synapse opens, and a guide
      explains how to link each file (one-time, links last forever)
"""

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QInputDialog, QLabel,
    QListWidget, QMenu, QMessageBox, QPushButton, QScrollArea, QVBoxLayout,
    QWidget,
)

from core import settings as settings_mod
from core.keymap import KEY_GROUPS
from core.settings import SHORTCUT_SELECTORS
from gui import config_io, theme
from gui.widgets import ADD, REMOVE, color_combo, secondary, tool_button

SYNAPSE_CANDIDATES = [
    Path(r"C:\Program Files\Razer\RazerAppEngine\RazerAppEngine.exe"),
    Path(r"C:\Program Files (x86)\Razer\Synapse3\WPFUI\Framework"
         r"\Razer Synapse 3 Host\Razer Synapse 3.exe"),
]

HYPERSHIFT_GUIDE = (
    "The folder with this set's files and Razer Synapse are now open.\n\n"
    "In Synapse (one time per key, the link then lasts forever):\n"
    "  1. Select your keyboard → CUSTOMIZE\n"
    "  2. Switch the layer switch to HYPERSHIFT\n"
    "  3. Click a key → LAUNCH → Program → pick that key's .vbs file\n"
    "  4. SAVE, repeat for the remaining keys\n\n"
    "Re-mapping colors later happens ONLY in this app — Synapse never\n"
    "needs to be touched again."
)


class ShortcutsTab(QWidget):
    def __init__(self, raw: dict, hypershift_available: bool):
        super().__init__()
        self.raw = raw
        self.hypershift_available = hypershift_available
        self._loading = False

        self.enabled = QCheckBox("Shortcuts enabled")
        self.enabled.toggled.connect(
            lambda on: self.raw["shortcuts"].__setitem__("enabled", on))

        self.set_list = QListWidget()
        self.set_list.currentRowChanged.connect(lambda *_: self._load_set())
        add_set = QPushButton(f"{ADD} Add set")
        add_set.clicked.connect(self._add_set)
        remove_set = secondary(QPushButton(f"{REMOVE} Remove set"))
        remove_set.clicked.connect(self._remove_set)

        left = QVBoxLayout()
        left.addWidget(QLabel("Shortcut sets"))
        left.addWidget(self.set_list, 1)
        left.addWidget(add_set)
        left.addWidget(remove_set)

        self.selector = QComboBox()
        self.selector.currentTextChanged.connect(self._store_selector)

        self.add_key_btn = secondary(QPushButton(f"{ADD} Add key"))
        self.add_key_btn.clicked.connect(self._add_key_menu)

        self.bindings_grid = QGridLayout()
        self.bindings_grid.setSpacing(theme.SPACE_S)
        bindings_host = QWidget()
        bindings_host.setLayout(self.bindings_grid)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(bindings_host)

        self.create_btn = QPushButton("Create shortcut files")
        self.create_btn.clicked.connect(self._create_files)
        self.guide_label = QLabel()
        self.guide_label.setProperty("hint", True)

        top_form = QHBoxLayout()
        top_form.addWidget(QLabel("Selector"))
        top_form.addWidget(self.selector, 1)
        top_form.addWidget(self.add_key_btn)

        right = QVBoxLayout()
        right.addLayout(top_form)
        right.addWidget(scroll, 1)
        right.addWidget(self.guide_label)
        right.addWidget(self.create_btn)

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
            self.set_list.addItem(f"{s['name']}   ({s['selector']})")
        if self._sets():
            self.set_list.setCurrentRow(min(row, len(self._sets()) - 1))
        self._load_set()

    def _selector_choices(self, current_selector: str | None) -> list[str]:
        choices = [s for s in SHORTCUT_SELECTORS if s != "hypershift"]
        if self.hypershift_available or current_selector == "hypershift":
            choices.append("hypershift")
        return choices

    def _load_set(self) -> None:
        current = self._current()
        self._loading = True
        for w in (self.selector, self.add_key_btn, self.create_btn):
            w.setEnabled(current is not None)
        self.selector.clear()
        if current:
            self.selector.addItems(self._selector_choices(current["selector"]))
            self.selector.setCurrentText(current["selector"])
            if current["selector"] == "hypershift":
                self.guide_label.setText(
                    "Hypershift set: create the files, then link them in Synapse "
                    "(a guide opens with the folder).")
            else:
                self.guide_label.setText(
                    "Normal selector: the daemon activates these hotkeys by "
                    "itself right after saving — nothing manual.")
        else:
            self.guide_label.setText("Add a set to begin.")
        self._rebuild_bindings()
        self._loading = False

    def _rebuild_bindings(self) -> None:
        while self.bindings_grid.count():
            item = self.bindings_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        current = self._current()
        if not current:
            return
        for i, (key, color) in enumerate(current["bindings"].items()):
            combo = color_combo(self.raw, color)
            combo.currentTextChanged.connect(
                lambda value, k=key: self._store_binding(k, value))
            remove = tool_button(REMOVE, "Remove this key")
            remove.clicked.connect(lambda _=False, k=key: self._remove_key(k))
            row, col = i % 8, (i // 8) * 3
            key_label = QLabel(key)
            key_label.setAlignment(Qt.AlignmentFlag.AlignRight
                                   | Qt.AlignmentFlag.AlignVCenter)
            self.bindings_grid.addWidget(key_label, row, col)
            self.bindings_grid.addWidget(combo, row, col + 1)
            self.bindings_grid.addWidget(remove, row, col + 2)
        self.bindings_grid.setRowStretch(8, 1)

    # -- actions -----------------------------------------------------------

    def _add_set(self) -> None:
        name, ok = QInputDialog.getText(self, "New shortcut set",
                                        "Set name (e.g. DUGA):")
        name = name.strip()
        if not ok or not name:
            return
        if any(s["name"].lower() == name.lower() for s in self._sets()):
            QMessageBox.warning(self, "Ultra Vivid", f"Set {name!r} already exists.")
            return
        self._sets().append({"name": name, "selector": "shift", "bindings": {}})
        self.reload()
        self.set_list.setCurrentRow(len(self._sets()) - 1)

    def _remove_set(self) -> None:
        row = self.set_list.currentRow()
        if row < 0:
            return
        del self._sets()[row]
        self.reload()

    def _store_selector(self) -> None:
        current = self._current()
        if current is None or self._loading or not self.selector.currentText():
            return
        current["selector"] = self.selector.currentText()
        self.set_list.currentItem().setText(
            f"{current['name']}   ({current['selector']})")
        self._load_set()

    def _add_key_menu(self) -> None:
        current = self._current()
        if current is None:
            return
        menu = QMenu(self)
        for group, keys in KEY_GROUPS.items():
            sub = menu.addMenu(group)
            for key in keys:
                action = sub.addAction(key)
                action.setEnabled(key not in current["bindings"])
                action.triggered.connect(
                    lambda _=False, k=key: self._add_key(k))
        menu.exec(self.add_key_btn.mapToGlobal(
            self.add_key_btn.rect().bottomLeft()))

    def _add_key(self, key: str) -> None:
        current = self._current()
        first_color = next(iter(self.raw["colors"]))
        current["bindings"][key] = first_color
        self._rebuild_bindings()

    def _remove_key(self, key: str) -> None:
        current = self._current()
        current["bindings"].pop(key, None)
        self._rebuild_bindings()

    def _store_binding(self, key: str, color: str) -> None:
        current = self._current()
        if current is not None and not self._loading:
            current["bindings"][key] = color

    def _create_files(self) -> None:
        """Owner flow steps 5-6: save, build the set's folder, then either
        confirm (daemon case) or open folder + Synapse + guide (hypershift)."""
        current = self._current()
        if current is None:
            return
        if not current["bindings"]:
            QMessageBox.warning(self, "Ultra Vivid", "Add at least one key first.")
            return
        try:
            config_io.save_raw(self.raw)
        except settings_mod.ConfigError as e:
            QMessageBox.warning(self, "Ultra Vivid", f"Fix the config first:\n\n{e}")
            return

        from resolver import write_set_folder
        cfg = settings_mod.parse(self.raw)
        shortcut_set = next(s for s in cfg.shortcut_sets
                            if s.name == current["name"])
        folder = write_set_folder(cfg, shortcut_set)

        if current["selector"] == "hypershift":
            os.startfile(folder)
            for candidate in SYNAPSE_CANDIDATES:
                if candidate.exists():
                    subprocess.Popen([str(candidate)])
                    break
            QMessageBox.information(self, f"Link {current['name']} in Synapse",
                                    HYPERSHIFT_GUIDE)
        else:
            QMessageBox.information(
                self, "Ultra Vivid",
                f"Files created in {folder}.\n\n"
                "The hotkeys are registered automatically by the daemon "
                "within a few seconds — nothing else to do.")
