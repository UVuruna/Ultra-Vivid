"""Location picker — DOMY Watch's city system over the 45k-city database.

Live search (type 2+ letters, click a suggestion) plus cascading
Continent / Subregion / Country / Region / City combos. Picking a city
fills latitude, longitude and the IANA timezone automatically — the
user NEVER types a timezone (a typo there would silently break every
daylight computation). Lat/lon stay fine-tunable.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QWidget,
)

from core.locations import LocationRepository, fold_name
from gui import theme

_NO_REGION = "—"                       # the country's direct cities
_MAX_RESULTS = 30


class LocationPicker(QWidget):
    """Edits raw["location"] in place; emits location_changed on a pick."""

    location_changed = Signal()

    def __init__(self, raw: dict):
        super().__init__()
        self.raw = raw
        self.repo = LocationRepository()
        self._loading = False

        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 City name… (e.g. Beograd, Niš, Tokyo)")
        self.search.textChanged.connect(self._filter_cities)
        self.results = QListWidget()
        self.results.hide()
        self.results.itemClicked.connect(self._pick_result)

        self.continent = QComboBox()
        self.subregion = QComboBox()
        self.country = QComboBox()
        self.region = QComboBox()
        self.city = QComboBox()

        self.latitude = QDoubleSpinBox()
        self.latitude.setRange(-90, 90)
        self.latitude.setDecimals(4)
        self.longitude = QDoubleSpinBox()
        self.longitude.setRange(-180, 180)
        self.longitude.setDecimals(4)
        self.tz_label = QLabel("")
        self.tz_label.setProperty("hint", True)
        for spin in (self.latitude, self.longitude):
            spin.valueChanged.connect(self._store_fine_tune)

        grid = QGridLayout()
        grid.setSpacing(theme.SPACE_S)
        rows = [("Continent", self.continent), ("Subregion", self.subregion),
                ("Country", self.country), ("Region", self.region),
                ("City", self.city)]
        for i, (label, combo) in enumerate(rows):
            grid.addWidget(QLabel(label), i, 0)
            grid.addWidget(combo, i, 1)
        grid.addWidget(QLabel("Lat / Lon"), len(rows), 0)
        fine = QHBoxLayout()
        fine.addWidget(self.latitude)
        fine.addWidget(self.longitude)
        grid.addLayout(fine, len(rows), 1)
        grid.addWidget(QLabel("Timezone"), len(rows) + 1, 0)
        grid.addWidget(self.tz_label, len(rows) + 1, 1)

        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setSpacing(theme.SPACE_S)
        layout.addWidget(self.search)
        layout.addWidget(self.results)
        layout.addLayout(grid)

        self._fill(self.continent, ())
        self.continent.currentTextChanged.connect(lambda _: self._on_level(1))
        self.subregion.currentTextChanged.connect(lambda _: self._on_level(2))
        self.country.currentTextChanged.connect(lambda _: self._on_level(3))
        self.region.currentTextChanged.connect(lambda _: self._on_level(4))
        self.city.currentTextChanged.connect(lambda _: self._on_city())

        self._loading = True
        self._on_level(1)
        self._restore_stored()
        self._loading = False

    # -- combos ------------------------------------------------------------

    def _fill(self, combo: QComboBox, path: tuple[str, ...], cities: bool = False) -> None:
        combo.blockSignals(True)
        combo.clear()
        try:
            children = self.repo.children(path)
        except KeyError:
            children = []
        combo.addItems(sorted(c.name for c in children if c.is_city == cities))
        combo.blockSignals(False)

    def _group_path(self) -> tuple[str, ...]:
        path = (self.continent.currentText(), self.subregion.currentText(),
                self.country.currentText())
        region = self.region.currentText()
        return path if region in ("", _NO_REGION) else path + (region,)

    def _on_level(self, level: int) -> None:
        if level <= 1:
            self._fill(self.subregion, (self.continent.currentText(),))
        if level <= 2:
            self._fill(self.country,
                       (self.continent.currentText(), self.subregion.currentText()))
        if level <= 3:
            country_path = (self.continent.currentText(),
                            self.subregion.currentText(), self.country.currentText())
            try:
                children = self.repo.children(country_path)
            except KeyError:
                children = []
            admins = sorted(c.name for c in children if not c.is_city)
            direct = any(c.is_city for c in children)
            self.region.blockSignals(True)
            self.region.clear()
            if direct:
                self.region.addItem(_NO_REGION)
            self.region.addItems(admins)
            self.region.blockSignals(False)
        self._fill(self.city, self._group_path(), cities=True)
        self._on_city()

    def _on_city(self) -> None:
        name = self.city.currentText()
        if not name or self._loading:
            return
        record = self.repo.record_at(self._group_path() + (name,))
        if record is None:
            return
        self._loading = True
        self.latitude.setValue(record.latitude)
        self.longitude.setValue(record.longitude)
        self._loading = False
        self.tz_label.setText(record.timezone)
        self.raw["location"] = {
            "name": record.name,
            "latitude": record.latitude,
            "longitude": record.longitude,
            "timezone": record.timezone,
        }
        self.location_changed.emit()

    def _store_fine_tune(self) -> None:
        if self._loading:
            return
        self.raw.setdefault("location", {})
        self.raw["location"]["latitude"] = self.latitude.value()
        self.raw["location"]["longitude"] = self.longitude.value()
        self.location_changed.emit()

    def _restore_stored(self) -> None:
        """Show the stored location; walk the combos to it by city name."""
        loc = self.raw.get("location", {})
        if not loc.get("name"):
            return
        self.tz_label.setText(loc.get("timezone", ""))
        self.latitude.setValue(loc.get("latitude", 0.0))
        self.longitude.setValue(loc.get("longitude", 0.0))
        wanted = fold_name(loc["name"])
        for folded, _display, path in self.repo.all_cities():
            if folded == wanted:
                self._walk_to(path)
                self.latitude.setValue(loc.get("latitude", 0.0))
                self.longitude.setValue(loc.get("longitude", 0.0))
                break

    # -- live search -------------------------------------------------------

    def _filter_cities(self, text: str) -> None:
        text = text.strip()
        if len(text) < 2:
            self.results.hide()
            return
        wanted = fold_name(text)
        matches = [(display, path)
                   for folded, display, path in self.repo.all_cities()
                   if wanted in folded]
        matches.sort(key=lambda m: (not fold_name(m[0]).startswith(wanted), m[0]))
        self.results.clear()
        for display, path in matches[:_MAX_RESULTS]:
            item = QListWidgetItem(f"{display}  —  {' / '.join(path[:-1])}")
            item.setData(Qt.ItemDataRole.UserRole, path)
            self.results.addItem(item)
        if matches:
            row_height = self.results.sizeHintForRow(0)
            self.results.setFixedHeight(
                min(150, self.results.count() * row_height + 10))
            self.results.show()
        else:
            self.results.hide()

    def _pick_result(self, item: QListWidgetItem) -> None:
        self._walk_to(tuple(item.data(Qt.ItemDataRole.UserRole)))
        self.results.hide()
        self.search.clear()

    def _walk_to(self, path: tuple[str, ...]) -> None:
        """Select the combos along a full city path; the city change
        handler then fills the record values."""
        was_loading = self._loading
        self._loading = False
        combos = [self.continent, self.subregion, self.country]
        for combo, segment in zip(combos, path):
            index = combo.findText(segment)
            if index < 0:
                self._loading = was_loading
                return
            combo.setCurrentIndex(index)
        tail = path[3:]
        if len(tail) == 2:
            index = self.region.findText(tail[0])
            if index < 0:
                self._loading = was_loading
                return
            self.region.setCurrentIndex(index)
        index = self.city.findText(path[-1])
        if index >= 0:
            self.city.setCurrentIndex(index)
        self._loading = was_loading
