# GUI Folder

## Purpose

PySide6 GUI application for configuring Ultra Vivid without editing config.json manually.

## Contents

- [GUI Setup Wizard](gui.md) - Main entry point and all tabs
- [profile_scanner.py](profile_scanner.py) - .orp file detection
- [config_writer.py](config_writer.py) - config.json read/write with schema migration
- [runner.py](runner.py) - Admin PowerShell invocation via UAC

## Usage

```
python -m gui.gui
```
