"""Import every module — a syntax/import error in a lazily-imported
module (e.g. core.tasks reached only via --install-tasks) must fail the
test suite, not surface only in a frozen build. Born from a real case:
core/tasks.py had an unterminated-string SyntaxError that PyInstaller
silently dropped, breaking the installed exe's --install-tasks.
"""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

MODULES = [
    "main",
    "resolver",
    "hotkey_daemon",
    "core.settings", "core.schedule", "core.solar", "core.apply",
    "core.actions", "core.keymap", "core.chroma", "core.locations",
    "core.paths", "core.tasks",
    "gui.app", "gui.main_window", "gui.theme", "gui.widgets",
    "gui.colors_tab", "gui.presets_tab", "gui.devices_tab",
    "gui.shortcuts_tab", "gui.location_picker", "gui.config_io",
]


@pytest.mark.parametrize("module", MODULES)
def test_module_imports(module):
    importlib.import_module(module)
