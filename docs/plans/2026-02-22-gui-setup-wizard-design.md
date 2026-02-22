# GUI Setup Wizard — Design Document

**Date:** 2026-02-22
**Status:** Approved

## Table of Contents

- [Overview](#overview)
- [Technology Stack](#technology-stack)
- [Architecture](#architecture)
- [UI Structure](#ui-structure)
  - [Tab: Setup](#tab-setup)
  - [Tab: Raspored (Schedule)](#tab-raspored-schedule)
  - [Tab: Tastature (F-keys)](#tab-tastature-f-keys)
  - [Tab: Ekstra](#tab-ekstra)
  - [StatusBar and Apply Button](#statusbar-and-apply-button)
- [Data Flow](#data-flow)
- [Config Schema Changes](#config-schema-changes)

<a id="overview"></a>

## Overview

A Python GUI application that replaces manual `config.json` editing and direct `setup.ps1` invocation. The GUI provides a visual interface for configuring Auto OpenRGB, then generates `config.json` and calls `setup.ps1` automatically.

**Goals:**
- Browse to OpenRGB installation folder
- Auto-detect existing OpenRGB profiles (`.orp` files)
- Configure three scheduling modes: time-based, keyboard shortcuts, extra profiles
- Write `config.json` and invoke `setup.ps1` (as Admin) with one click

**Non-goals:**
- Replacing `setup.ps1` logic — the GUI is a front-end only
- Real-time profile switching — that remains in VBS/Task Scheduler

<a id="technology-stack"></a>

## Technology Stack

- **Language:** Python 3
- **GUI Framework:** tkinter (built-in) or PyQt5/PyQt6
- **No additional runtime required** beyond Python installation

<a id="architecture"></a>

## Architecture

```
📁 gui/
  🔧 gui.py              ← Entry point, MainWindow class
  🔧 profile_scanner.py  ← Scans .orp files from OpenRGB data folder
  🔧 config_writer.py    ← Serializes GUI state to config.json
  🔧 runner.py           ← Invokes setup.ps1 as Admin (UAC prompt)
```

**On startup:** GUI reads existing `config.json` (if present) and pre-populates all fields, preserving previous configuration.

**On Apply:** GUI writes `config.json`, then calls `setup.ps1` elevated via PowerShell's `-Verb RunAs`.

<a id="ui-structure"></a>

## UI Structure

Main window has a **Tabbed UI** with 4 tabs and a persistent bottom bar.

<a id="tab-setup"></a>

### Tab: Setup

Handles OpenRGB installation path and profile detection.

```
OpenRGB putanja:
[C:\Program Files\OpenRGB\OpenRGB.exe    ] [Browse...]

Status: ✅ OpenRGB pronađen

Profili pronađeni (12):
┌─────────────────────────────────────────┐
│ 0-black  │ 1-blue  │ 2-cyan  │ ...     │
└─────────────────────────────────────────┘
            [🔄 Reskenuj profile]
```

**Behavior:**
- Browse button opens file dialog filtering for `OpenRGB.exe`
- `profile_scanner.py` looks for `.orp` files in `%APPDATA%\OpenRGB\` (or adjacent to exe)
- Detected profile names populate dropdowns in all other tabs
- "Reskenuj" rescans without restarting the app

<a id="tab-raspored-schedule"></a>

### Tab: Raspored (Schedule)

Configures time-based automatic profile switching.

```
Početni sat: [03 ▼]    Broj slotova: [8 ▼]
[↺ Resetuj na podjednake intervale]

┌──────────────────────────────────────────────────────┐
│ Slot │ Početak │ Kraj (auto) │ Profil                │
├──────────────────────────────────────────────────────┤
│  1   │ [03:00] │ 05:59       │ [1-blue          ▼]  │
│  2   │ [06:00] │ 08:59       │ [2-cyan          ▼]  │
│  3   │ [09:30] │ 11:59  ⚠️   │ [3-green         ▼]  │
└──────────────────────────────────────────────────────┘
⚠️ Vremenska rupa: 09:00-09:29 nije pokrivena
```

**Behavior:**
- "Početni sat" + "Broj slotova" → default auto-calculation (equal intervals)
- "Resetuj" resets start times to equal intervals
- Each slot's "Početak" is manually editable (spinbox HH:MM)
- "Kraj" is read-only, auto-calculated as `next_slot_start - 1 minute`
- Warning shown if gaps exist between consecutive slots
- Table rows added/removed dynamically when slot count changes

**Config impact:** Stores actual per-slot start times (not just `startHour`). See [Config Schema Changes](#config-schema-changes).

<a id="tab-tastature-f-keys"></a>

### Tab: Tastature (F-keys)

Assigns OpenRGB profiles to F1-F12 keyboard shortcuts.

```
Rainbow profili - dodeli na F tastere:

F1:  [UC-01-00F    ▼]   F7:  [UC-07-...  ▼]
F2:  [UC-02-08F   ▼]   F8:  [UC-08-...  ▼]
F3:  [UC-03-...   ▼]   F9:  [UC-09-...  ▼]
F4:  [UC-04-...   ▼]   F10: [UC-10-...  ▼]
F5:  [UC-05-...   ▼]   F11: [UC-11-...  ▼]
F6:  [UC-06-...   ▼]   F12: [UC-12-...  ▼]

ℹ️ VBS fajlovi za ove profile generišu se u rainbow/
```

**Behavior:**
- 12 dropdowns (F1-F12), each populated from Setup tab profile list
- Generates `rainbow/F1.vbs` through `rainbow/F12.vbs` via `setup.ps1`

<a id="tab-ekstra"></a>

### Tab: Ekstra

Manages manual/extra profiles outside the schedule.

```
Ručni profili (pozivaju se VBS-om ili prečicom):

┌────────────────────────────────────────────────────┐
│ Naziv VBS-a │ Profil              │ Akcija         │
├────────────────────────────────────────────────────┤
│ light       │ [9-white      ▼]   │ [🗑]           │
│ dark        │ [0-black      ▼]   │ [🗑]           │
└────────────────────────────────────────────────────┘
[+ Dodaj novi]
```

**Behavior:**
- Dynamic list — rows can be added (name input + profile dropdown) or deleted
- Generates one VBS per row in `cycle/` folder (extra entries)

<a id="statusbar-and-apply-button"></a>

### StatusBar and Apply Button

Persistent across all tabs, always visible at the bottom.

```
Status: Poslednji setup: 2026-02-22 14:30        [▶ Primeni]
```

**Apply behavior:**
1. Validate: OpenRGB path exists, no schedule gaps (warn but don't block)
2. Write `config.json`
3. Invoke `setup.ps1` as Admin via `powershell -Verb RunAs`
4. Show result in status bar: `✅ Setup završen` or `❌ Greška: <message>`

<a id="data-flow"></a>

## Data Flow

```
Korisnik bira OpenRGB.exe
  ↓
profile_scanner.py skenira .orp fajlove
  ↓
Dropdowns se popunjavaju u svim tabovima
  ↓
Korisnik konfiguriše raspored, F-taste, extras
  ↓
[Primeni] klik
  ↓
config_writer.py → config.json
  ↓
runner.py → powershell -Verb RunAs setup.ps1
  ↓
Status bar: uspeh ili greška
```

<a id="config-schema-changes"></a>

## Config Schema Changes

The schedule now stores per-slot start times instead of only `startHour`:

**Current:**
```json
"schedules": {
    "startHour": 3,
    "items": [
        { "taskName": "OpenRGB zora", "vbsName": "1-dawn", "profile": "1-blue" }
    ]
}
```

**New (adds `startTime` per item):**
```json
"schedules": {
    "items": [
        { "taskName": "OpenRGB zora", "vbsName": "1-dawn", "profile": "1-blue", "startTime": "03:00" },
        { "taskName": "OpenRGB jutro", "vbsName": "2-morning", "profile": "2-cyan", "startTime": "06:00" }
    ]
}
```

`setup.ps1` (specifically `create-tasks.ps1`) must be updated to read `startTime` per item instead of calculating from `startHour`.
