# GUI Setup Wizard

**Script:** [GUI entry point](gui.py)

## Purpose

Python tkinter GUI for configuring Auto OpenRGB without manually editing config.json.
Detects OpenRGB profiles, configures schedule/F-keys/extras, writes config.json, and
invokes setup.ps1 as Administrator.

## Dependencies

- Python 3.7+
- tkinter (built-in with Python on Windows)

## Usage

Run from project root:

```
python -m gui.gui
```

## Files

- [GUI entry point](gui.py) - Main window, all tabs
- [profile_scanner.py](profile_scanner.py) - Detects .orp profile files
- [config_writer.py](config_writer.py) - Reads/writes config.json
- [runner.py](runner.py) - Invokes setup.ps1 as Admin
