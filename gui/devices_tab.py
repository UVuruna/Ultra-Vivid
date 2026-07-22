"""Devices tab — which OpenRGB devices the schedule paints.

Lists devices live from the SDK server with checkboxes; the check state
is translated to the config's include/exclude filter. When the server is
unreachable the stored filter is shown read-only with a retry button.
"""

import dataclasses

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QLabel, QListWidget, QListWidgetItem, QPushButton,
    QVBoxLayout, QWidget,
)

from core import apply as rgb
from core import settings as settings_mod
from gui import theme


class DevicesTab(QWidget):
    def __init__(self, raw: dict):
        super().__init__()
        self.raw = raw

        self.status = QLabel()
        self.status.setProperty("hint", True)
        self.device_list = QListWidget()
        self.device_list.itemChanged.connect(self._store)

        refresh = QPushButton("↻ Refresh from OpenRGB")
        refresh.setProperty("secondary", True)
        refresh.clicked.connect(self.reload)

        hint = QLabel("Checked devices follow the schedule; unchecked are left "
                      "alone (e.g. a keyboard managed by Razer Synapse).")
        hint.setProperty("hint", True)

        chroma_cfg = self.raw.setdefault(
            "chroma", {"enabled": False, "followSchedule": True})
        self.chroma_enabled = QCheckBox(
            "Color the Razer keyboard via Chroma (Synapse bindings untouched)")
        self.chroma_enabled.setChecked(bool(chroma_cfg.get("enabled", False)))
        self.chroma_enabled.toggled.connect(
            lambda on: self.raw["chroma"].__setitem__("enabled", on))
        self.chroma_follow = QCheckBox("Chroma keyboard follows the schedule")
        self.chroma_follow.setChecked(bool(chroma_cfg.get("followSchedule", True)))
        self.chroma_follow.toggled.connect(
            lambda on: self.raw["chroma"].__setitem__("followSchedule", on))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_M, theme.SPACE_M, theme.SPACE_M, theme.SPACE_M)
        layout.setSpacing(theme.SPACE_S)
        layout.addWidget(QLabel("OpenRGB devices"))
        layout.addWidget(self.device_list, 1)
        layout.addWidget(refresh)
        layout.addWidget(self.status)
        layout.addWidget(hint)
        layout.addSpacing(theme.SPACE_S)
        layout.addWidget(QLabel("Razer Chroma module"))
        layout.addWidget(self.chroma_enabled)
        layout.addWidget(self.chroma_follow)

        self.reload()

    def _selected_by_filter(self, name: str) -> bool:
        f = self.raw["devices"]
        matched = any(n.lower() in name.lower() for n in f.get("names", []))
        return not matched if f.get("mode") == "exclude" else matched

    def reload(self) -> None:
        self.device_list.blockSignals(True)
        self.device_list.clear()
        try:
            cfg = settings_mod.parse(self.raw)
            quick = dataclasses.replace(
                cfg, openrgb=dataclasses.replace(cfg.openrgb, connect_retries=1))
            client = rgb.connect(quick)
            try:
                names = [d.name for d in client.devices]
            finally:
                client.disconnect()
            for name in names:
                item = QListWidgetItem(name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked if self._selected_by_filter(name)
                    else Qt.CheckState.Unchecked)
                self.device_list.addItem(item)
            self.status.setText(f"Connected — {len(names)} devices.")
        except Exception as e:
            self.status.setText(
                f"OpenRGB server unreachable ({e}). Stored filter: "
                f"{self.raw['devices']['mode']} {self.raw['devices']['names']}")
        self.device_list.blockSignals(False)

    def _store(self, _item) -> None:
        """Translate check states into an exclude list (unchecked names)."""
        unchecked = [
            self.device_list.item(i).text()
            for i in range(self.device_list.count())
            if self.device_list.item(i).checkState() != Qt.CheckState.Checked
        ]
        self.raw["devices"] = {"mode": "exclude", "names": unchecked}
