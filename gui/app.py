"""Ultra Vivid GUI entry point.

Run from the project root:
    python -m gui.app
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import QApplication

from gui import theme
from gui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(theme.app_qss())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
