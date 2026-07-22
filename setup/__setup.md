# Build Pipeline

**Folder:** [setup/](.)

## Purpose

Builds UltraVivid into a distributable Windows installer (`UltraVivid_Setup.exe`).

## Contents

- [svg_to_ico.py](svg_to_ico.py) — Generate `UltraVivid.ico` from `assets/logo.svg`
- [create_cert.py](create_cert.py) — Create a self-signed code signing certificate
- [build.py](build.py) — Main build pipeline (ICO → PyInstaller → sign → NSIS)
- [installer.nsi](installer.nsi) — NSIS installer script
- 📁 cert/ — Certificate files (gitignored, created by `create_cert.py`)

## Prerequisites

```
pip install -r requirements.txt
```

Install NSIS: https://nsis.sourceforge.io/ — add to PATH or install to default location.

## Usage

### First time setup (optional — for code signing)

```
python setup/create_cert.py
```

Creates `setup/cert/UltraVivid.pfx`. Requires `setup/cert/password.txt` with the
certificate password (create manually before running).

### Provide the app icon

Place `logo.svg` in the `assets/` folder. The build pipeline generates the
`.ico` from it. If the SVG is missing, the build proceeds without an icon.

### Run the full build

```
python setup/build.py
```

Output: `dist/UltraVivid_Setup.exe`

## Build Steps

| Step | Script | Output |
|------|--------|--------|
| 1. Generate ICO | `svg_to_ico.py` | `assets/UltraVivid.ico` |
| 2. PyInstaller | `pyinstaller` | `dist/UltraVivid/` |
| 3. Sign exe | `signtool` | signed exe (skipped if no cert) |
| 4. NSIS installer | `makensis` | `dist/UltraVivid_Setup.exe` |

## Version

Version is read from `version.py` at project root. Update it before building.

## Certificate Notes

- `setup/cert/` is gitignored — never commit certificates
- Self-signed cert will show a SmartScreen warning (expected for personal tools)
- For trusted signing, replace with a commercial certificate
