"""Presets tab — the base entity of Ultra Vivid: named color presets.

Left: preset list with live swatches. Right: editor for the selected
preset — rename and its color list (one color = whole setup; N colors =
round-robin across selected devices).
"""

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from gui import theme


def _secondary(button: QPushButton) -> QPushButton:
    button.setProperty("secondary", True)
    return button


class PresetsTab(QWidget):
    presets_changed = Signal()

    def __init__(self, raw: dict):
        super().__init__()
        self.raw = raw

        self.preset_list = QListWidget()
        self.preset_list.currentItemChanged.connect(lambda *_: self._load_colors())

        add_btn = QPushButton("＋ New preset")
        add_btn.clicked.connect(self._add_preset)
        rename_btn = _secondary(QPushButton("Rename"))
        rename_btn.clicked.connect(self._rename_preset)
        remove_btn = _secondary(QPushButton("Remove"))
        remove_btn.clicked.connect(self._remove_preset)

        left = QVBoxLayout()
        left.addWidget(QLabel("Color presets"))
        left.addWidget(self.preset_list, 1)
        row = QHBoxLayout()
        for b in (add_btn, rename_btn, remove_btn):
            row.addWidget(b)
        left.addLayout(row)

        self.color_list = QListWidget()
        self.color_list.itemDoubleClicked.connect(lambda *_: self._edit_color())
        add_color = _secondary(QPushButton("＋ Add color"))
        add_color.clicked.connect(self._add_color)
        edit_color = _secondary(QPushButton("Edit"))
        edit_color.clicked.connect(self._edit_color)
        del_color = _secondary(QPushButton("Remove"))
        del_color.clicked.connect(self._remove_color)

        hint = QLabel("One color paints every selected device.\n"
                      "Several colors are distributed round-robin across devices.")
        hint.setProperty("hint", True)

        right = QVBoxLayout()
        right.addWidget(QLabel("Colors of the selected preset"))
        right.addWidget(self.color_list, 1)
        crow = QHBoxLayout()
        for b in (add_color, edit_color, del_color):
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

    def _presets(self) -> dict:
        return self.raw["colorPresets"]

    def _current_name(self) -> str | None:
        item = self.preset_list.currentItem()
        return item.text() if item else None

    def reload(self) -> None:
        self.preset_list.clear()
        for name, colors in self._presets().items():
            self.preset_list.addItem(
                QListWidgetItem(theme.swatch_icon(colors[0]), name))
        if self.preset_list.count():
            self.preset_list.setCurrentRow(0)
        self._load_colors()

    def _load_colors(self) -> None:
        self.color_list.clear()
        name = self._current_name()
        if name is None:
            return
        for color in self._presets()[name]:
            self.color_list.addItem(
                QListWidgetItem(theme.swatch_icon(color), f"#{color.upper()}"))

    # -- preset actions ----------------------------------------------------

    def _add_preset(self) -> None:
        name, ok = QInputDialog.getText(self, "New preset", "Preset name:")
        name = name.strip()
        if not ok or not name:
            return
        if name in self._presets():
            QMessageBox.warning(self, "Ultra Vivid", f"Preset {name!r} already exists.")
            return
        color = QColorDialog.getColor(QColor("#8B5CF6"), self, f"Color for {name}")
        if not color.isValid():
            return
        self._presets()[name] = [color.name()[1:].upper()]
        self.reload()
        self.preset_list.setCurrentRow(self.preset_list.count() - 1)
        self.presets_changed.emit()

    def _rename_preset(self) -> None:
        old = self._current_name()
        if old is None:
            return
        new, ok = QInputDialog.getText(self, "Rename preset", "New name:", text=old)
        new = new.strip()
        if not ok or not new or new == old:
            return
        if new in self._presets():
            QMessageBox.warning(self, "Ultra Vivid", f"Preset {new!r} already exists.")
            return
        presets = self._presets()
        presets[new] = presets.pop(old)
        self._rename_references(old, new)
        self.reload()
        self.presets_changed.emit()

    def _remove_preset(self) -> None:
        name = self._current_name()
        if name is None:
            return
        used = self._where_used(name)
        if used:
            QMessageBox.warning(
                self, "Ultra Vivid",
                f"Preset {name!r} is still used by: {', '.join(used)}.\n"
                "Re-map those first.")
            return
        del self._presets()[name]
        self.reload()
        self.presets_changed.emit()

    def _where_used(self, name: str) -> list[str]:
        used = []
        s = self.raw.get("schedule", {})
        if any(slot.get("preset") == name for slot in s.get("hours", [])):
            used.append("schedule.hours")
        if name in s.get("weekdays", {}).values():
            used.append("schedule.weekdays")
        if any(slot.get("preset") == name for slot in s.get("monthdays", [])):
            used.append("schedule.monthdays")
        if name in s.get("months", {}).values():
            used.append("schedule.months")
        d = s.get("daylight", {})
        if name in d.get("day", []) or name == d.get("twilight") or name in d.get("night", []):
            used.append("schedule.daylight")
        for i, st in enumerate(self.raw.get("shortcuts", {}).get("sets", [])):
            if name in st.get("bindings", {}).values():
                used.append(f"shortcuts set {i}")
        return used

    def _rename_references(self, old: str, new: str) -> None:
        s = self.raw.get("schedule", {})
        for slot in s.get("hours", []) + s.get("monthdays", []):
            if slot.get("preset") == old:
                slot["preset"] = new
        for section in (s.get("weekdays", {}), s.get("months", {})):
            for k, v in section.items():
                if v == old:
                    section[k] = new
        d = s.get("daylight", {})
        d["day"] = [new if p == old else p for p in d.get("day", [])]
        if d.get("twilight") == old:
            d["twilight"] = new
        d["night"] = [new if p == old else p for p in d.get("night", [])]
        for st in self.raw.get("shortcuts", {}).get("sets", []):
            for k, v in st.get("bindings", {}).items():
                if v == old:
                    st["bindings"][k] = new

    # -- color actions -----------------------------------------------------

    def _add_color(self) -> None:
        name = self._current_name()
        if name is None:
            return
        color = QColorDialog.getColor(QColor("#FFFFFF"), self, f"Add color to {name}")
        if color.isValid():
            self._presets()[name].append(color.name()[1:].upper())
            self._load_colors()
            self.presets_changed.emit()

    def _edit_color(self) -> None:
        name = self._current_name()
        row = self.color_list.currentRow()
        if name is None or row < 0:
            return
        current = self._presets()[name][row]
        color = QColorDialog.getColor(QColor(f"#{current}"), self, "Edit color")
        if color.isValid():
            self._presets()[name][row] = color.name()[1:].upper()
            self.reload()
            self.presets_changed.emit()

    def _remove_color(self) -> None:
        name = self._current_name()
        row = self.color_list.currentRow()
        if name is None or row < 0:
            return
        if len(self._presets()[name]) == 1:
            QMessageBox.warning(self, "Ultra Vivid", "A preset needs at least one color.")
            return
        del self._presets()[name][row]
        self._load_colors()
        self.presets_changed.emit()
