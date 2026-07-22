"""Presets tab — a PRESET is a RULE (owner terminology): a trigger
grouping (hours / weekdays / monthdays / months / daylight) whose slots
reference defined colors. Several presets can exist; exactly ONE is
active — the resolver follows the active one.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QInputDialog, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea,
    QSpinBox, QStackedWidget, QVBoxLayout, QWidget,
)

from core.settings import MONTH_KEYS, PRESET_TYPES, WEEKDAY_KEYS
from gui import theme
from gui.location_picker import LocationPicker
from gui.widgets import (
    ADD, REMOVE, ColorSequence, color_combo, combo_value,
    refresh_color_combo, secondary, tool_button,
)

_OFF_HINT = "Uncovered time = ALL RGB OFF."

_EMPTY_PRESET = {"name": "", "type": "hours", "hours": [], "weekdays": {},
                 "monthdays": [], "months": {}, "daylight": {}}


class _SlotRowsEditor(QWidget):
    """Shared editor for from/to/color slot lists (hours and monthdays)."""

    def __init__(self, tab: "PresetsTab", key: str, lo: int, hi: int,
                 unit_label: str, hint: str):
        super().__init__()
        self.tab, self.key, self.lo, self.hi = tab, key, lo, hi
        self.rows: list[tuple[QSpinBox, QSpinBox, QComboBox]] = []

        self.grid = QGridLayout()
        self.grid.setSpacing(theme.SPACE_S)
        for col, title in enumerate([f"From {unit_label}", f"To {unit_label}", "Color", ""]):
            label = QLabel(title)
            label.setProperty("hint", True)
            self.grid.addWidget(label, 0, col)

        add = secondary(QPushButton(f"{ADD} Add slot"))
        add.clicked.connect(lambda: (self._add_row(self.lo, self.lo, None), self.store()))
        hint_label = QLabel(hint)
        hint_label.setProperty("hint", True)

        layout = QVBoxLayout(self)
        layout.addLayout(self.grid)
        layout.addWidget(add)
        layout.addWidget(hint_label)
        layout.addStretch(1)

    def _add_row(self, start: int, end: int, color: str | None) -> None:
        row_index = len(self.rows) + 1
        from_spin, to_spin = QSpinBox(), QSpinBox()
        for spin, value in ((from_spin, start), (to_spin, end)):
            spin.setRange(self.lo, self.hi)
            spin.setValue(value)
            spin.valueChanged.connect(self.store)
        combo = color_combo(self.tab.raw, color)
        combo.currentTextChanged.connect(self.store)
        remove = tool_button(REMOVE, "Remove this slot")
        widgets = (from_spin, to_spin, combo)
        remove.clicked.connect(lambda: self._remove_row(widgets, remove))
        for col, w in enumerate([*widgets, remove]):
            self.grid.addWidget(w, row_index, col)
        self.rows.append(widgets)

    def _remove_row(self, widgets, remove_btn) -> None:
        self.rows.remove(widgets)
        for w in (*widgets, remove_btn):
            self.grid.removeWidget(w)
            w.deleteLater()
        self.store()

    def load(self) -> None:
        while self.grid.count() > 4:  # keep the 4 header labels
            item = self.grid.takeAt(4)
            if item.widget():
                item.widget().deleteLater()
        self.rows.clear()
        preset = self.tab.current_preset()
        if preset:
            for slot in preset.get(self.key, []):
                self._add_row(slot["from"], slot["to"], slot["color"])

    def store(self) -> None:
        preset = self.tab.current_preset()
        if preset is not None and not self.tab.loading:
            preset[self.key] = [
                {"from": f.value(), "to": t.value(), "color": c.currentText()}
                for f, t, c in self.rows
            ]


class _MappingEditor(QWidget):
    """Shared editor for fixed key->color mappings (weekdays and months)."""

    def __init__(self, tab: "PresetsTab", key: str, entries: list[str], labels: list[str]):
        super().__init__()
        self.tab, self.key, self.entries = tab, key, entries
        self.combos: dict[str, QComboBox] = {}
        grid = QGridLayout(self)
        grid.setSpacing(theme.SPACE_S)
        columns = 2 if len(entries) > 7 else 1
        per_column = (len(entries) + columns - 1) // columns
        for i, (entry, label) in enumerate(zip(entries, labels)):
            combo = color_combo(self.tab.raw, None)
            combo.currentTextChanged.connect(self.store)
            self.combos[entry] = combo
            row, col = i % per_column, (i // per_column) * 2
            grid.addWidget(QLabel(label), row, col)
            grid.addWidget(combo, row, col + 1)
        grid.setRowStretch(per_column, 1)

    def load(self) -> None:
        preset = self.tab.current_preset()
        stored = preset.get(self.key, {}) if preset else {}
        for entry, combo in self.combos.items():
            refresh_color_combo(combo, self.tab.raw, stored.get(entry))

    def store(self) -> None:
        preset = self.tab.current_preset()
        if preset is not None and not self.tab.loading:
            preset[self.key] = {
                entry: combo.currentText() for entry, combo in self.combos.items()
            }


class _DaylightEditor(QWidget):
    """Day arc + separate MORNING and EVENING civil twilight colors +
    night arc + the DOMY-style city picker (timezone never typed)."""

    def __init__(self, tab: "PresetsTab"):
        super().__init__()
        self.tab = tab
        self.day = ColorSequence(tab.raw, "☀️ Day colors (sunrise → sunset, solar-noon centered)", self.store)
        self.night = ColorSequence(tab.raw, "🌙 Night colors (empty = RGB off at night)", self.store)
        self.twilight_morning = color_combo(tab.raw, None, allow_none=True)
        self.twilight_evening = color_combo(tab.raw, None, allow_none=True)
        for combo in (self.twilight_morning, self.twilight_evening):
            combo.currentTextChanged.connect(self.store)

        twilight = QGridLayout()
        twilight.addWidget(QLabel("🌅 Morning twilight (civil, −6°)"), 0, 0)
        twilight.addWidget(self.twilight_morning, 0, 1)
        twilight.addWidget(QLabel("🌆 Evening twilight (civil, −6°)"), 1, 0)
        twilight.addWidget(self.twilight_evening, 1, 1)

        self.location = LocationPicker(tab.raw)

        hint = QLabel("Sun events are computed locally (no internet). The day arc is split\n"
                      "equally, so its center follows the TRUE solar noon of your city.")
        hint.setProperty("hint", True)

        layout = QVBoxLayout(self)
        layout.setSpacing(theme.SPACE_M)
        layout.addWidget(self.day)
        layout.addLayout(twilight)
        layout.addWidget(self.night)
        layout.addWidget(QLabel("📍 Location"))
        layout.addWidget(self.location)
        layout.addWidget(hint)
        layout.addStretch(1)

    def load(self) -> None:
        preset = self.tab.current_preset()
        d = preset.setdefault("daylight", {}) if preset else {}
        self.day.set_values(d.get("day", []))
        self.night.set_values(d.get("night", []))
        refresh_color_combo(self.twilight_morning, self.tab.raw,
                            d.get("twilightMorning"), allow_none=True)
        refresh_color_combo(self.twilight_evening, self.tab.raw,
                            d.get("twilightEvening"), allow_none=True)

    def store(self) -> None:
        preset = self.tab.current_preset()
        if preset is not None and not self.tab.loading:
            preset["daylight"] = {
                "day": self.day.values(),
                "twilightMorning": combo_value(self.twilight_morning),
                "twilightEvening": combo_value(self.twilight_evening),
                "night": self.night.values(),
            }


class PresetsTab(QWidget):
    def __init__(self, raw: dict):
        super().__init__()
        self.raw = raw
        self.loading = False

        self.enabled = QCheckBox("Schedule enabled (the active preset runs)")
        self.enabled.toggled.connect(
            lambda on: self.raw.__setitem__("scheduleEnabled", on))

        self.preset_list = QListWidget()
        self.preset_list.currentRowChanged.connect(lambda *_: self._load_preset())
        add_btn = QPushButton(f"{ADD} Add preset")
        add_btn.clicked.connect(self._add_preset)
        remove_btn = secondary(QPushButton(f"{REMOVE} Remove"))
        remove_btn.clicked.connect(self._remove_preset)
        activate_btn = QPushButton("⭐ Set active")
        activate_btn.clicked.connect(self._set_active)

        left = QVBoxLayout()
        left.addWidget(QLabel("Presets (rules) — ⭐ marks the active one"))
        left.addWidget(self.preset_list, 1)
        left.addWidget(activate_btn)
        row = QHBoxLayout()
        row.addWidget(add_btn)
        row.addWidget(remove_btn)
        left.addLayout(row)

        self.type_combo = QComboBox()
        self.type_combo.addItems(PRESET_TYPES)
        self.type_combo.currentTextChanged.connect(self._type_changed)

        weekday_labels = ["Monday", "Tuesday", "Wednesday", "Thursday",
                          "Friday", "Saturday", "Sunday"]
        month_labels = ["January", "February", "March", "April", "May", "June",
                        "July", "August", "September", "October", "November", "December"]

        self.editors = {
            "hours": _SlotRowsEditor(self, "hours", 0, 23, "hour",
                                     f"`to` is exclusive and may wrap midnight. {_OFF_HINT}"),
            "weekdays": _MappingEditor(self, "weekdays", WEEKDAY_KEYS, weekday_labels),
            "monthdays": _SlotRowsEditor(self, "monthdays", 1, 31, "day",
                                         f"Both bounds inclusive; first match wins. {_OFF_HINT}"),
            "months": _MappingEditor(self, "months", MONTH_KEYS, month_labels),
            "daylight": _DaylightEditor(self),
        }

        self.stack = QStackedWidget()
        for name in PRESET_TYPES:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(self.editors[name])
            self.stack.addWidget(scroll)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Trigger type"))
        type_row.addWidget(self.type_combo, 1)

        right = QVBoxLayout()
        right.addLayout(type_row)
        right.addWidget(self.stack, 1)

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

    def _presets(self) -> list[dict]:
        return self.raw["presets"]

    def current_preset(self) -> dict | None:
        row = self.preset_list.currentRow()
        return self._presets()[row] if 0 <= row < len(self._presets()) else None

    def reload(self) -> None:
        self.enabled.setChecked(bool(self.raw.get("scheduleEnabled", True)))
        row = max(self.preset_list.currentRow(), 0)
        self.preset_list.clear()
        active = self.raw.get("activePreset")
        for p in self._presets():
            star = "⭐ " if p["name"] == active else ""
            self.preset_list.addItem(QListWidgetItem(f"{star}{p['name']}   ({p['type']})"))
        if self._presets():
            self.preset_list.setCurrentRow(min(row, len(self._presets()) - 1))
        self._load_preset()

    def _load_preset(self) -> None:
        preset = self.current_preset()
        self.loading = True
        self.type_combo.setEnabled(preset is not None)
        if preset:
            self.type_combo.setCurrentText(preset["type"])
            self.stack.setCurrentIndex(PRESET_TYPES.index(preset["type"]))
        for editor in self.editors.values():
            editor.load()
        self.loading = False

    # -- actions -----------------------------------------------------------

    def _type_changed(self, ptype: str) -> None:
        preset = self.current_preset()
        if preset is not None and not self.loading:
            preset["type"] = ptype
            self.stack.setCurrentIndex(PRESET_TYPES.index(ptype))
            self.reload()

    def _add_preset(self) -> None:
        name, ok = QInputDialog.getText(self, "New preset",
                                        "Preset name (e.g. Work week):")
        name = name.strip()
        if not ok or not name:
            return
        if any(p["name"].lower() == name.lower() for p in self._presets()):
            QMessageBox.warning(self, "Ultra Vivid", f"Preset {name!r} already exists.")
            return
        preset = dict(_EMPTY_PRESET, name=name,
                      hours=[], weekdays={}, monthdays=[], months={}, daylight={})
        self._presets().append(preset)
        if self.raw.get("activePreset") is None:
            self.raw["activePreset"] = name
        self.reload()
        self.preset_list.setCurrentRow(len(self._presets()) - 1)

    def _remove_preset(self) -> None:
        row = self.preset_list.currentRow()
        if row < 0:
            return
        removed = self._presets()[row]["name"]
        del self._presets()[row]
        if self.raw.get("activePreset") == removed:
            self.raw["activePreset"] = (
                self._presets()[0]["name"] if self._presets() else None)
        self.reload()

    def _set_active(self) -> None:
        preset = self.current_preset()
        if preset is not None:
            self.raw["activePreset"] = preset["name"]
            self.reload()
