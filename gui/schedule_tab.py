"""Schedule tab — ONE grouping type per schedule (owner spec).

A type selector switches between five editors: hours, weekdays,
monthdays, months, daylight. Each editor reads from and writes straight
into the raw config dict; preset choices refresh whenever presets change.
"""

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QSpinBox, QStackedWidget,
    QVBoxLayout, QWidget,
)

from core.settings import MONTH_KEYS, SCHEDULE_TYPES, WEEKDAY_KEYS
from gui import theme

_NONE = "(none)"
_OFF_HINT = "Uncovered time = ALL RGB OFF."


def preset_combo(raw: dict, selected: str | None, allow_none: bool = False) -> QComboBox:
    combo = QComboBox()
    if allow_none:
        combo.addItem(_NONE)
    for name, colors in raw["colorPresets"].items():
        combo.addItem(theme.swatch_icon(colors[0]), name)
    combo.setCurrentText(selected if selected else _NONE if allow_none else combo.currentText())
    return combo


def combo_value(combo: QComboBox) -> str | None:
    text = combo.currentText()
    return None if text == _NONE else text


class _SlotRowsEditor(QWidget):
    """Shared editor for from/to/preset slot lists (hours and monthdays)."""

    def __init__(self, raw: dict, key: str, lo: int, hi: int, unit_label: str, hint: str):
        super().__init__()
        self.raw, self.key, self.lo, self.hi = raw, key, lo, hi
        self.rows: list[tuple[QSpinBox, QSpinBox, QComboBox]] = []

        self.grid = QGridLayout()
        self.grid.setSpacing(theme.SPACE_S)
        for col, title in enumerate([f"From {unit_label}", f"To {unit_label}", "Preset", ""]):
            label = QLabel(title)
            label.setProperty("hint", True)
            self.grid.addWidget(label, 0, col)

        add = QPushButton("＋ Add slot")
        add.setProperty("secondary", True)
        add.clicked.connect(lambda: (self._add_row(self.lo, self.lo, None), self.store()))
        hint_label = QLabel(hint)
        hint_label.setProperty("hint", True)

        layout = QVBoxLayout(self)
        layout.addLayout(self.grid)
        layout.addWidget(add)
        layout.addWidget(hint_label)
        layout.addStretch(1)

    def _add_row(self, start: int, end: int, preset: str | None) -> None:
        row_index = len(self.rows) + 1
        from_spin, to_spin = QSpinBox(), QSpinBox()
        for spin, value in ((from_spin, start), (to_spin, end)):
            spin.setRange(self.lo, self.hi)
            spin.setValue(value)
            spin.valueChanged.connect(self.store)
        combo = preset_combo(self.raw, preset)
        combo.currentTextChanged.connect(self.store)
        remove = QPushButton("✕")
        remove.setProperty("secondary", True)
        remove.setFixedWidth(36)
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
        for widgets in list(self.rows):
            for w in widgets:
                self.grid.removeWidget(w)
                w.deleteLater()
        self.rows.clear()
        # remove buttons are found and deleted with their row widgets above;
        # rebuild rows fresh from config
        while self.grid.count() > 4:  # keep the 4 header labels
            item = self.grid.takeAt(4)
            if item.widget():
                item.widget().deleteLater()
        for slot in self.raw["schedule"].get(self.key, []):
            self._add_row(slot["from"], slot["to"], slot["preset"])

    def store(self) -> None:
        self.raw["schedule"][self.key] = [
            {"from": f.value(), "to": t.value(), "preset": c.currentText()}
            for f, t, c in self.rows
        ]


class _MappingEditor(QWidget):
    """Shared editor for fixed key->preset mappings (weekdays and months)."""

    def __init__(self, raw: dict, key: str, entries: list[str], labels: list[str]):
        super().__init__()
        self.raw, self.key, self.entries = raw, key, entries
        self.combos: dict[str, QComboBox] = {}
        grid = QGridLayout(self)
        grid.setSpacing(theme.SPACE_S)
        columns = 2 if len(entries) > 7 else 1
        per_column = (len(entries) + columns - 1) // columns
        for i, (entry, label) in enumerate(zip(entries, labels)):
            combo = preset_combo(raw, None)
            combo.currentTextChanged.connect(self.store)
            self.combos[entry] = combo
            row, col = i % per_column, (i // per_column) * 2
            grid.addWidget(QLabel(label), row, col)
            grid.addWidget(combo, row, col + 1)
        grid.setRowStretch(per_column, 1)

    def load(self) -> None:
        stored = self.raw["schedule"].get(self.key, {})
        for entry, combo in self.combos.items():
            if entry in stored:
                combo.setCurrentText(stored[entry])

    def store(self) -> None:
        self.raw["schedule"][self.key] = {
            entry: combo.currentText() for entry, combo in self.combos.items()
        }


class _PresetSequence(QWidget):
    """Ordered list of preset combos (daylight day/night color sequences)."""

    def __init__(self, raw: dict, title: str, on_change):
        super().__init__()
        self.raw, self.on_change = raw, on_change
        self.combos: list[QComboBox] = []
        self.rows = QVBoxLayout()
        add = QPushButton("＋")
        add.setProperty("secondary", True)
        add.setFixedWidth(36)
        add.clicked.connect(lambda: (self._add(None), self.on_change()))
        head = QHBoxLayout()
        head.addWidget(QLabel(title))
        head.addStretch(1)
        head.addWidget(add)
        layout = QVBoxLayout(self)
        layout.addLayout(head)
        layout.addLayout(self.rows)

    def _add(self, preset: str | None) -> None:
        combo = preset_combo(self.raw, preset)
        combo.currentTextChanged.connect(self.on_change)
        remove = QPushButton("✕")
        remove.setProperty("secondary", True)
        remove.setFixedWidth(36)
        row = QHBoxLayout()
        row.addWidget(combo, 1)
        row.addWidget(remove)
        container = QWidget()
        container.setLayout(row)
        remove.clicked.connect(
            lambda: (self.combos.remove(combo), container.deleteLater(), self.on_change()))
        self.rows.addWidget(container)
        self.combos.append(combo)

    def set_values(self, presets: list[str]) -> None:
        while self.rows.count():
            item = self.rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.combos.clear()
        for p in presets:
            self._add(p)

    def values(self) -> list[str]:
        return [c.currentText() for c in self.combos]


class _DaylightEditor(QWidget):
    def __init__(self, raw: dict):
        super().__init__()
        self.raw = raw
        self.day = _PresetSequence(raw, "Day colors (sunrise → sunset, solar-noon centered)", self.store)
        self.night = _PresetSequence(raw, "Night colors (empty = RGB off at night)", self.store)
        self.twilight = preset_combo(raw, None, allow_none=True)
        self.twilight.currentTextChanged.connect(self.store)

        self.lat = QDoubleSpinBox(); self.lat.setRange(-90, 90); self.lat.setDecimals(4)
        self.lon = QDoubleSpinBox(); self.lon.setRange(-180, 180); self.lon.setDecimals(4)
        self.tz = QLineEdit(); self.tz.setPlaceholderText("Europe/Belgrade")
        self.place = QLineEdit(); self.place.setPlaceholderText("City")
        for w in (self.lat, self.lon):
            w.valueChanged.connect(self.store)
        for w in (self.tz, self.place):
            w.textChanged.connect(self.store)

        loc = QGridLayout()
        loc.addWidget(QLabel("Location"), 0, 0)
        loc.addWidget(self.place, 0, 1)
        loc.addWidget(QLabel("Lat / Lon"), 1, 0)
        lat_lon = QHBoxLayout(); lat_lon.addWidget(self.lat); lat_lon.addWidget(self.lon)
        loc.addLayout(lat_lon, 1, 1)
        loc.addWidget(QLabel("Timezone"), 2, 0)
        loc.addWidget(self.tz, 2, 1)

        twilight_row = QHBoxLayout()
        twilight_row.addWidget(QLabel("Civil twilight color (−6°)"))
        twilight_row.addWidget(self.twilight, 1)

        hint = QLabel("Sun events are computed locally (no internet). The day arc is\n"
                      "split equally, so its center follows the TRUE solar noon.")
        hint.setProperty("hint", True)

        layout = QVBoxLayout(self)
        layout.addWidget(self.day)
        layout.addLayout(twilight_row)
        layout.addWidget(self.night)
        layout.addLayout(loc)
        layout.addWidget(hint)
        layout.addStretch(1)

    def load(self) -> None:
        d = self.raw["schedule"].setdefault(
            "daylight", {"day": [], "twilight": None, "night": []})
        self.day.set_values(d.get("day", []))
        self.night.set_values(d.get("night", []))
        self.twilight.setCurrentText(d.get("twilight") or _NONE)
        loc = self.raw.get("location", {})
        self.place.setText(loc.get("name", ""))
        self.lat.setValue(loc.get("latitude", 0.0))
        self.lon.setValue(loc.get("longitude", 0.0))
        self.tz.setText(loc.get("timezone", ""))

    def store(self) -> None:
        self.raw["schedule"]["daylight"] = {
            "day": self.day.values(),
            "twilight": combo_value(self.twilight),
            "night": self.night.values(),
        }
        self.raw["location"] = {
            "name": self.place.text().strip(),
            "latitude": self.lat.value(),
            "longitude": self.lon.value(),
            "timezone": self.tz.text().strip(),
        }


class ScheduleTab(QWidget):
    def __init__(self, raw: dict):
        super().__init__()
        self.raw = raw

        self.enabled = QCheckBox("Schedule enabled")
        self.enabled.toggled.connect(
            lambda on: self.raw["schedule"].__setitem__("enabled", on))

        self.type_combo = QComboBox()
        self.type_combo.addItems(SCHEDULE_TYPES)
        self.type_combo.currentTextChanged.connect(self._type_changed)

        weekday_labels = ["Monday", "Tuesday", "Wednesday", "Thursday",
                          "Friday", "Saturday", "Sunday"]
        month_labels = ["January", "February", "March", "April", "May", "June",
                        "July", "August", "September", "October", "November", "December"]

        self.editors = {
            "hours": _SlotRowsEditor(raw, "hours", 0, 23, "hour",
                                     f"`to` is exclusive and may wrap midnight. {_OFF_HINT}"),
            "weekdays": _MappingEditor(raw, "weekdays", WEEKDAY_KEYS, weekday_labels),
            "monthdays": _SlotRowsEditor(raw, "monthdays", 1, 31, "day",
                                         f"Both bounds inclusive; first match wins. {_OFF_HINT}"),
            "months": _MappingEditor(raw, "months", MONTH_KEYS, month_labels),
            "daylight": _DaylightEditor(raw),
        }

        self.stack = QStackedWidget()
        for name in SCHEDULE_TYPES:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(self.editors[name])
            self.stack.addWidget(scroll)

        top = QHBoxLayout()
        top.addWidget(self.enabled)
        top.addStretch(1)
        top.addWidget(QLabel("Grouping type"))
        top.addWidget(self.type_combo)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_M, theme.SPACE_M, theme.SPACE_M, theme.SPACE_M)
        layout.setSpacing(theme.SPACE_M)
        layout.addLayout(top)
        layout.addWidget(self.stack, 1)

        self.reload()

    def _type_changed(self, stype: str) -> None:
        self.raw["schedule"]["type"] = stype
        self.stack.setCurrentIndex(SCHEDULE_TYPES.index(stype))

    def reload(self) -> None:
        """Rebuild editors from config (also called when presets change)."""
        s = self.raw["schedule"]
        self.enabled.setChecked(bool(s.get("enabled", True)))
        self.type_combo.blockSignals(True)
        self.type_combo.setCurrentText(s["type"])
        self.type_combo.blockSignals(False)
        self.stack.setCurrentIndex(SCHEDULE_TYPES.index(s["type"]))
        for editor in self.editors.values():
            editor.load()
