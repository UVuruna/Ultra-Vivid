"""Colors tab — the DEFINED COLORS of the app (owner terminology).

A default palette ships with the config; the user can add fully custom
colors. Presets (rules), shortcuts and Chroma all reference these by
name. NOT presets — a preset is a rule and lives in the Presets tab.
"""

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from gui import theme
from gui.widgets import ADD, EDIT, REMOVE, secondary


class ColorsTab(QWidget):
    colors_changed = Signal()

    def __init__(self, raw: dict):
        super().__init__()
        self.raw = raw

        self.color_list = QListWidget()
        self.color_list.currentItemChanged.connect(lambda *_: self._load_values())

        add_btn = QPushButton(f"{ADD} New color")
        add_btn.clicked.connect(self._add_color)
        rename_btn = secondary(QPushButton("✏️ Rename"))
        rename_btn.clicked.connect(self._rename_color)
        remove_btn = secondary(QPushButton(f"{REMOVE} Remove"))
        remove_btn.clicked.connect(self._remove_color)

        left = QVBoxLayout()
        left.addWidget(QLabel("Defined colors"))
        left.addWidget(self.color_list, 1)
        row = QHBoxLayout()
        for b in (add_btn, rename_btn, remove_btn):
            row.addWidget(b)
        left.addLayout(row)

        self.value_list = QListWidget()
        self.value_list.itemDoubleClicked.connect(lambda *_: self._edit_value())
        add_value = secondary(QPushButton(f"{ADD} Add hex"))
        add_value.clicked.connect(self._add_value)
        edit_value = secondary(QPushButton(f"{EDIT} Edit"))
        edit_value.clicked.connect(self._edit_value)
        del_value = secondary(QPushButton(f"{REMOVE} Remove"))
        del_value.clicked.connect(self._remove_value)

        hint = QLabel("One hex value paints every selected device.\n"
                      "Several values are distributed round-robin across devices.")
        hint.setProperty("hint", True)

        right = QVBoxLayout()
        right.addWidget(QLabel("Hex values of the selected color"))
        right.addWidget(self.value_list, 1)
        crow = QHBoxLayout()
        for b in (add_value, edit_value, del_value):
            crow.addWidget(b)
        right.addLayout(crow)
        right.addWidget(hint)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_M, theme.SPACE_M, theme.SPACE_M, theme.SPACE_M)
        layout.setSpacing(theme.SPACE_M)
        layout.addLayout(left, 1)
        layout.addLayout(right, 1)

        self.reload()

    # -- data helpers ------------------------------------------------------

    def _colors(self) -> dict:
        return self.raw["colors"]

    def _current_name(self) -> str | None:
        item = self.color_list.currentItem()
        return item.text() if item else None

    def reload(self) -> None:
        self.color_list.clear()
        for name, values in self._colors().items():
            self.color_list.addItem(
                QListWidgetItem(theme.swatch_icon(values[0]), name))
        if self.color_list.count():
            self.color_list.setCurrentRow(0)
        self._load_values()

    def _load_values(self) -> None:
        self.value_list.clear()
        name = self._current_name()
        if name is None:
            return
        for value in self._colors()[name]:
            self.value_list.addItem(
                QListWidgetItem(theme.swatch_icon(value), f"#{value.upper()}"))

    # -- color actions -----------------------------------------------------

    def _add_color(self) -> None:
        name, ok = QInputDialog.getText(self, "New color", "Color name:")
        name = name.strip()
        if not ok or not name:
            return
        if name in self._colors():
            QMessageBox.warning(self, "Ultra Vivid", f"Color {name!r} already exists.")
            return
        picked = QColorDialog.getColor(QColor("#8B5CF6"), self, f"Value for {name}")
        if not picked.isValid():
            return
        self._colors()[name] = [picked.name()[1:].upper()]
        self.reload()
        self.color_list.setCurrentRow(self.color_list.count() - 1)
        self.colors_changed.emit()

    def _rename_color(self) -> None:
        old = self._current_name()
        if old is None:
            return
        new, ok = QInputDialog.getText(self, "Rename color", "New name:", text=old)
        new = new.strip()
        if not ok or not new or new == old:
            return
        if new in self._colors():
            QMessageBox.warning(self, "Ultra Vivid", f"Color {new!r} already exists.")
            return
        colors = self._colors()
        colors[new] = colors.pop(old)
        self._rename_references(old, new)
        self.reload()
        self.colors_changed.emit()

    def _remove_color(self) -> None:
        name = self._current_name()
        if name is None:
            return
        used = self._where_used(name)
        if used:
            QMessageBox.warning(
                self, "Ultra Vivid",
                f"Color {name!r} is still used by: {', '.join(used)}.\n"
                "Re-map those first.")
            return
        del self._colors()[name]
        self.reload()
        self.colors_changed.emit()

    def _where_used(self, name: str) -> list[str]:
        used = []
        for preset in self.raw.get("presets", []):
            hits = (
                any(s.get("color") == name for s in preset.get("hours", []))
                or name in preset.get("weekdays", {}).values()
                or any(s.get("color") == name for s in preset.get("monthdays", []))
                or name in preset.get("months", {}).values()
                or name in preset.get("daylight", {}).get("day", [])
                or name == preset.get("daylight", {}).get("twilightMorning")
                or name == preset.get("daylight", {}).get("twilightEvening")
                or name in preset.get("daylight", {}).get("night", [])
            )
            if hits:
                used.append(f"preset {preset['name']!r}")
        for st in self.raw.get("shortcuts", {}).get("sets", []):
            if any(b.get("color") == name for b in st.get("bindings", {}).values()):
                used.append(f"shortcut set {st['name']!r}")
        return used

    def _rename_references(self, old: str, new: str) -> None:
        for preset in self.raw.get("presets", []):
            for slot in preset.get("hours", []) + preset.get("monthdays", []):
                if slot.get("color") == old:
                    slot["color"] = new
            for section in (preset.get("weekdays", {}), preset.get("months", {})):
                for k, v in section.items():
                    if v == old:
                        section[k] = new
            d = preset.get("daylight", {})
            if d:
                d["day"] = [new if c == old else c for c in d.get("day", [])]
                for tk in ("twilightMorning", "twilightEvening"):
                    if d.get(tk) == old:
                        d[tk] = new
                d["night"] = [new if c == old else c for c in d.get("night", [])]
        for st in self.raw.get("shortcuts", {}).get("sets", []):
            for binding in st.get("bindings", {}).values():
                if binding.get("color") == old:
                    binding["color"] = new

    # -- hex value actions -------------------------------------------------

    def _add_value(self) -> None:
        name = self._current_name()
        if name is None:
            return
        picked = QColorDialog.getColor(QColor("#FFFFFF"), self, f"Add value to {name}")
        if picked.isValid():
            self._colors()[name].append(picked.name()[1:].upper())
            self._load_values()
            self.colors_changed.emit()

    def _edit_value(self) -> None:
        name = self._current_name()
        row = self.value_list.currentRow()
        if name is None or row < 0:
            return
        current = self._colors()[name][row]
        picked = QColorDialog.getColor(QColor(f"#{current}"), self, "Edit value")
        if picked.isValid():
            self._colors()[name][row] = picked.name()[1:].upper()
            self.reload()
            self.colors_changed.emit()

    def _remove_value(self) -> None:
        name = self._current_name()
        row = self.value_list.currentRow()
        if name is None or row < 0:
            return
        if len(self._colors()[name]) == 1:
            QMessageBox.warning(self, "Ultra Vivid", "A color needs at least one hex value.")
            return
        del self._colors()[name][row]
        self._load_values()
        self.colors_changed.emit()
