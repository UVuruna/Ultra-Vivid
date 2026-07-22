"""Ultra Vivid theme — DESIGN.md tokens and the app QSS.

Dark-first, one accent (vivid violet — the app is ABOUT color, the chrome
stays calm so the preset swatches carry the vividness). All values are
tokens here, never literals in component code (root Rule #4).
"""

from pathlib import Path

from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtCore import Qt

_CHECK_SVG = (Path(__file__).parent.parent / "assets" / "check.svg").as_posix()

# -- Color tokens (DESIGN.md dark surface ramp) ---------------------------
SURFACE_0 = "#141420"        # window background (navy-tinted charcoal)
SURFACE_1 = "#1D1D2B"        # cards, panels
SURFACE_2 = "#252537"        # raised elements, inputs
SURFACE_3 = "#2C2C42"        # highest elevation / hover
BORDER = "rgba(255,255,255,0.10)"
TEXT_PRIMARY = "#F5F5F5"
TEXT_SECONDARY = "#A7A7B4"

ACCENT = "#8B5CF6"           # vivid violet
ACCENT_LIGHT = "#A78BFA"
ACCENT_DARK = "#6D3EE8"
ACCENT_GLOW = "rgba(139,92,246,0.35)"

SUCCESS = "#22C55E"
WARNING = "#F59E0B"
ERROR = "#EF4444"

RADIUS_CONTROL = 8
RADIUS_CARD = 14
SPACE_S = 8
SPACE_M = 16
SPACE_L = 24

SWATCH_SIZE = 18             # px, preset color chips in combos/lists

FONT_STACK = '"Inter", "Segoe UI Variable", "Segoe UI"'


def app_qss() -> str:
    """The full application stylesheet, tokens interpolated."""
    return f"""
    QWidget {{
        background: {SURFACE_0};
        color: {TEXT_PRIMARY};
        font-family: {FONT_STACK};
        font-size: 14px;
    }}
    QLabel {{ background: transparent; }}
    QLabel[hint="true"] {{ color: {TEXT_SECONDARY}; font-size: 12px; }}

    QTabWidget::pane {{
        border: 1px solid {BORDER};
        border-radius: {RADIUS_CARD}px;
        background: {SURFACE_1};
        top: -1px;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {TEXT_SECONDARY};
        padding: {SPACE_S}px {SPACE_M}px;
        border-radius: {RADIUS_CONTROL}px;
        margin-right: 4px;
        font-weight: 600;
    }}
    QTabBar::tab:selected {{ color: {TEXT_PRIMARY}; background: {SURFACE_2}; }}
    QTabBar::tab:hover:!selected {{ color: {TEXT_PRIMARY}; }}

    QPushButton {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {ACCENT}, stop:1 {ACCENT_DARK});
        border: none;
        border-radius: {RADIUS_CONTROL}px;
        padding: {SPACE_S}px {SPACE_M}px;
        color: {TEXT_PRIMARY};
        font-weight: 600;
    }}
    QPushButton:hover {{ background: {ACCENT_LIGHT}; }}
    QPushButton:pressed {{ background: {ACCENT_DARK}; }}
    QPushButton:disabled {{ background: {SURFACE_2}; color: {TEXT_SECONDARY}; }}
    QPushButton[secondary="true"] {{
        background: {SURFACE_2};
        border: 1px solid {BORDER};
        font-weight: 500;
    }}
    QPushButton[secondary="true"]:hover {{ background: {SURFACE_3}; }}

    QComboBox, QSpinBox, QLineEdit, QDoubleSpinBox, QTimeEdit {{
        background: {SURFACE_2};
        border: 1px solid {BORDER};
        border-radius: {RADIUS_CONTROL}px;
        padding: 6px 10px;
        selection-background-color: {ACCENT};
    }}
    QComboBox:focus, QSpinBox:focus, QLineEdit:focus, QDoubleSpinBox:focus {{
        border: 1px solid {ACCENT};
    }}
    QComboBox::drop-down {{ border: none; width: 24px; }}
    QComboBox QAbstractItemView {{
        background: {SURFACE_2};
        border: 1px solid {BORDER};
        border-radius: {RADIUS_CONTROL}px;
        selection-background-color: {ACCENT};
    }}

    QListWidget, QTableWidget, QScrollArea {{
        background: {SURFACE_1};
        border: 1px solid {BORDER};
        border-radius: {RADIUS_CONTROL}px;
    }}
    QListWidget::item {{ padding: 6px 8px; border-radius: 6px; }}
    QListWidget::item:selected {{ background: {ACCENT}; color: {TEXT_PRIMARY}; }}
    QHeaderView::section {{
        background: {SURFACE_2};
        color: {TEXT_SECONDARY};
        border: none;
        padding: 6px;
        font-weight: 600;
    }}
    QTableWidget {{ gridline-color: {BORDER}; }}

    QCheckBox::indicator, QListWidget::indicator {{
        width: 18px; height: 18px;
        border-radius: 5px;
        border: 2px solid {TEXT_SECONDARY};
        background: {SURFACE_2};
    }}
    QCheckBox::indicator:hover, QListWidget::indicator:hover {{
        border-color: {ACCENT_LIGHT};
    }}
    QCheckBox::indicator:checked, QListWidget::indicator:checked {{
        background: {ACCENT};
        border-color: {ACCENT};
        image: url("{_CHECK_SVG}");
    }}
    QCheckBox:disabled {{ color: {TEXT_SECONDARY}; }}
    QCheckBox::indicator:disabled {{
        border-color: {BORDER};
        background: {SURFACE_1};
    }}

    QStatusBar {{ color: {TEXT_SECONDARY}; }}
    QScrollBar:vertical {{
        background: transparent; width: 10px; margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {SURFACE_3}; border-radius: 5px; min-height: 24px;
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    """


def swatch_icon(hex_color: str, size: int = SWATCH_SIZE) -> QIcon:
    """Rounded color chip used to preview a preset color in lists/combos."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(f"#{hex_color}"))
    painter.setPen(QColor(255, 255, 255, 40))
    painter.drawRoundedRect(0, 0, size - 1, size - 1, 5, 5)
    painter.end()
    return QIcon(pixmap)
