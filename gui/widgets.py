"""Small shared GUI building blocks (Rule #5): color combos, secondary
buttons, and the ordered color sequence editor with ⬆⬇ reordering."""

from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from gui import theme

NONE_ITEM = "(none)"

# Emoji glyphs for the small action buttons (owner spec: visible and
# intuitive). One vocabulary for the whole app:
ADD, REMOVE, EDIT, UP, DOWN, REFRESH = "➕", "🗑️", "🎨", "⬆️", "⬇️", "🔄"


def secondary(button: QPushButton) -> QPushButton:
    button.setProperty("secondary", True)
    return button


def tool_button(glyph: str, tooltip: str) -> QPushButton:
    button = secondary(QPushButton(glyph))
    button.setFixedWidth(40)
    button.setToolTip(tooltip)
    return button


def color_combo(raw: dict, selected: str | None, allow_none: bool = False) -> QComboBox:
    """Combo of the defined colors, each with its swatch chip."""
    combo = QComboBox()
    if allow_none:
        combo.addItem(NONE_ITEM)
    for name, values in raw["colors"].items():
        combo.addItem(theme.swatch_icon(values[0]), name)
    if selected:
        combo.setCurrentText(selected)
    elif allow_none:
        combo.setCurrentText(NONE_ITEM)
    return combo


def combo_value(combo: QComboBox) -> str | None:
    text = combo.currentText()
    return None if text == NONE_ITEM else text


def binding_combo(raw: dict, binding: dict | None) -> QComboBox:
    """Combo for a shortcut binding: every defined COLOR (with swatch)
    followed by every PRESET (rule, 🕑 prefix). The selected binding
    dict is read back with binding_from_combo."""
    from PySide6.QtCore import Qt

    combo = QComboBox()
    for name, values in raw["colors"].items():
        combo.addItem(theme.swatch_icon(values[0]), name)
        combo.setItemData(combo.count() - 1, ("color", name), Qt.ItemDataRole.UserRole)
    if raw.get("presets"):
        combo.insertSeparator(combo.count())
        for preset in raw["presets"]:
            combo.addItem(f"🕑 {preset['name']}")
            combo.setItemData(combo.count() - 1, ("preset", preset["name"]),
                              Qt.ItemDataRole.UserRole)
    if binding:
        kind, name = next(iter(binding.items()))
        for i in range(combo.count()):
            if combo.itemData(i, Qt.ItemDataRole.UserRole) == (kind, name):
                combo.setCurrentIndex(i)
                break
    return combo


def binding_from_combo(combo: QComboBox) -> dict | None:
    from PySide6.QtCore import Qt
    data = combo.currentData(Qt.ItemDataRole.UserRole)
    return {data[0]: data[1]} if data else None


def refresh_color_combo(combo: QComboBox, raw: dict, selected: str | None,
                        allow_none: bool = False) -> None:
    """Rebuild a color combo's item list from the CURRENT colors dict —
    combos built once at construction would never see newly created
    colors. Keeps the given selection, signals blocked."""
    combo.blockSignals(True)
    combo.clear()
    if allow_none:
        combo.addItem(NONE_ITEM)
    for name, values in raw["colors"].items():
        combo.addItem(theme.swatch_icon(values[0]), name)
    if selected:
        combo.setCurrentText(selected)
    elif allow_none:
        combo.setCurrentText(NONE_ITEM)
    combo.blockSignals(False)


class ColorSequence(QWidget):
    """Ordered list of color combos (daylight day/night arcs) with
    ➕ add, 🗑 remove and ⬆⬇ reorder on every row."""

    def __init__(self, raw: dict, title: str, on_change):
        super().__init__()
        self.raw, self.on_change = raw, on_change
        self.combos: list[QComboBox] = []
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(theme.SPACE_S)

        add = tool_button(ADD, "Add a color to the sequence")
        add.clicked.connect(lambda: (self._add(None), self._emit()))
        head = QHBoxLayout()
        head.addWidget(QLabel(title))
        head.addStretch(1)
        head.addWidget(add)

        layout = QVBoxLayout(self)
        layout.setSpacing(theme.SPACE_S)
        layout.addLayout(head)
        layout.addLayout(self.rows_layout)

    def _emit(self) -> None:
        self.on_change()

    def _add(self, color: str | None) -> None:
        combo = color_combo(self.raw, color)
        combo.currentTextChanged.connect(self._emit)
        up = tool_button(UP, "Move earlier in the sequence")
        down = tool_button(DOWN, "Move later in the sequence")
        remove = tool_button(REMOVE, "Remove this color")

        row = QHBoxLayout()
        row.addWidget(combo, 1)
        for b in (up, down, remove):
            row.addWidget(b)
        container = QWidget()
        container.setLayout(row)

        up.clicked.connect(lambda: self._move(combo, -1))
        down.clicked.connect(lambda: self._move(combo, +1))
        remove.clicked.connect(
            lambda: (self.combos.remove(combo), container.deleteLater(), self._emit()))
        self.rows_layout.addWidget(container)
        self.combos.append(combo)

    def _move(self, combo: QComboBox, delta: int) -> None:
        index = self.combos.index(combo)
        target = index + delta
        if not (0 <= target < len(self.combos)):
            return
        values = self.values()
        values[index], values[target] = values[target], values[index]
        self.set_values(values)
        self._emit()

    def set_values(self, colors: list[str]) -> None:
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.combos.clear()
        for c in colors:
            self._add(c)

    def values(self) -> list[str]:
        return [c.currentText() for c in self.combos]
