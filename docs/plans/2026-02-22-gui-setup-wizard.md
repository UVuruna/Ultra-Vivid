# GUI Setup Wizard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Python tkinter GUI that replaces manual config.json editing — browse for OpenRGB.exe, auto-detect .orp profiles, configure schedule/F-keys/extras, then write config.json and invoke setup.ps1.

**Architecture:** 4-file Python module in `gui/` folder. GUI is pure front-end — all actual setup logic stays in existing PowerShell scripts. Config schema gets `startTime` per schedule item (replaces calculated `startHour`). PowerShell `create-tasks.ps1` updated to read per-item times.

**Tech Stack:** Python 3, tkinter (built-in), json, subprocess, os

---

### Task 1: Create `gui/profile_scanner.py`

**Files:**
- Create: `gui/profile_scanner.py`

**What it does:** Given an OpenRGB.exe path, finds the OpenRGB user data folder and returns a sorted list of profile names (filename without `.orp` extension).

**OpenRGB data folder locations to check (in order):**
1. `%APPDATA%\OpenRGB\` — standard install
2. Same folder as `OpenRGB.exe` — portable install

**Step 1: Create the file**

```python
# profile_scanner.py - Scan OpenRGB .orp profile files

import os


def scan_profiles(openrgb_exe_path: str) -> list[str]:
    """Return sorted list of profile names found near OpenRGB installation."""
    candidates = _get_candidate_dirs(openrgb_exe_path)
    for folder in candidates:
        profiles = _scan_dir(folder)
        if profiles:
            return profiles
    return []


def _get_candidate_dirs(openrgb_exe_path: str) -> list[str]:
    appdata = os.environ.get("APPDATA", "")
    return [
        os.path.join(appdata, "OpenRGB"),
        os.path.dirname(openrgb_exe_path),
    ]


def _scan_dir(folder: str) -> list[str]:
    if not os.path.isdir(folder):
        return []
    names = [
        os.path.splitext(f)[0]
        for f in os.listdir(folder)
        if f.lower().endswith(".orp")
    ]
    return sorted(names)
```

**Step 2: Manual smoke-test** (no pytest needed for this simple scanner)

Run in Python REPL:
```python
from gui.profile_scanner import scan_profiles
print(scan_profiles(r"C:\Program Files\OpenRGB\OpenRGB.exe"))
# Expected: list of profile names like ['0-black', '1-blue', ...]
# If OpenRGB not installed: []
```

**Step 3: Commit**
```bash
git add gui/profile_scanner.py
git commit -m "feat(gui): add profile_scanner - detect .orp files from OpenRGB data folder"
```

---

### Task 2: Create `gui/config_writer.py`

**Files:**
- Create: `gui/config_writer.py`
- Read first: `config.json` (to understand current schema)

**What it does:** Takes GUI state dict and writes `config.json` with the new schema (per-item `startTime` instead of root-level `startHour`).

**New config.json schema for schedules:**
```json
"schedules": {
    "items": [
        { "taskName": "OpenRGB zora", "vbsName": "1-dawn", "profile": "1-blue", "startTime": "03:00" }
    ]
}
```

Note: `rainbow` section keeps `startHour` — it uses it differently (auto-selector, not Task Scheduler times).

**Step 1: Create the file**

```python
# config_writer.py - Write config.json from GUI state

import json
import os


def write_config(config_path: str, state: dict) -> None:
    """Write config.json from GUI state dict.

    state format:
    {
        "openRGBPath": "C:\\...\\OpenRGB.exe",
        "schedules": [
            {"taskName": "OpenRGB zora", "vbsName": "1-dawn", "profile": "1-blue", "startTime": "03:00"},
            ...
        ],
        "extras": [
            {"vbsName": "light", "profile": "9-white"},
            ...
        ],
        "rainbow": [
            {"vbsName": "F1", "profile": "UC-01-00F"},
            ...
        ]
    }
    """
    config = {
        "openRGBPath": state["openRGBPath"],
        "schedules": {
            "items": state["schedules"]
        },
        "extras": state["extras"],
        "rainbow": {
            "startHour": 3,
            "items": state["rainbow"]
        }
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def read_config(config_path: str) -> dict | None:
    """Read config.json and return GUI state dict, or None if file missing."""
    if not os.path.isfile(config_path):
        return None
    with open(config_path, encoding="utf-8") as f:
        raw = json.load(f)

    # Handle both old schema (startHour) and new schema (startTime per item)
    schedule_items = raw.get("schedules", {}).get("items", [])
    start_hour = raw.get("schedules", {}).get("startHour", 3)
    count = len(schedule_items)
    duration = 24 // count if count else 3

    schedules = []
    for i, item in enumerate(schedule_items):
        if "startTime" in item:
            start_time = item["startTime"]
        else:
            # Migrate old schema: calculate from startHour
            hour = (start_hour + duration * i) % 24
            start_time = f"{hour:02d}:00"
        schedules.append({
            "taskName": item.get("taskName", ""),
            "vbsName": item.get("vbsName", ""),
            "profile": item.get("profile", ""),
            "startTime": start_time,
        })

    return {
        "openRGBPath": raw.get("openRGBPath", ""),
        "schedules": schedules,
        "extras": raw.get("extras", []),
        "rainbow": raw.get("rainbow", {}).get("items", []),
    }
```

**Step 2: Commit**
```bash
git add gui/config_writer.py
git commit -m "feat(gui): add config_writer - read/write config.json with per-item startTime schema"
```

---

### Task 3: Update `lib/create-tasks.ps1` for new schema

**Files:**
- Modify: `lib/create-tasks.ps1`

**What changes:** Currently calculates `$hour` from `$startHour + $duration * $i`. Must now read `startTime` from each item directly.

**Read the file first**, then replace the daily tasks loop:

**Old code (lines ~30-50):**
```powershell
$startHour = [int]$config.schedules.startHour
$count = $items.Count
$duration = [int][math]::Floor(24 / $count)

for ($i = 0; $i -lt $count; $i++) {
    $item = $items[$i]
    $taskName = $item.taskName
    $prof = $item.profile

    # Calculate time from startHour and position
    $hour = [int](($startHour + $duration * $i) % 24)
    $time = "{0:D2}:00" -f $hour
```

**New code:**
```powershell
for ($i = 0; $i -lt $items.Count; $i++) {
    $item = $items[$i]
    $taskName = $item.taskName
    $prof = $item.profile

    # Read startTime directly from config item (format: "HH:MM")
    $time = $item.startTime
```

**Step 1: Edit `lib/create-tasks.ps1`** — remove the `$startHour`, `$count`, `$duration` lines, replace the `$hour`/`$time` calculation with `$time = $item.startTime`.

**Step 2: Test manually** — run setup.ps1 with existing config.json after running the GUI to generate new schema config. Verify tasks appear in Task Scheduler with correct times.

**Step 3: Commit**
```bash
git add lib/create-tasks.ps1
git commit -m "feat(lib): create-tasks reads startTime per item instead of calculating from startHour"
```

---

### Task 4: Update `lib/generate-bat.ps1` for new schema

**Files:**
- Modify: `lib/generate-bat.ps1`

**What changes:** `New-TimeVbs` function uses `$StartHour` parameter to calculate time ranges for `Select Case`. Must now accept actual start times per item.

**Old function signature:**
```powershell
function New-TimeVbs {
    param (
        [array]$Items,
        [int]$StartHour,
        ...
    )
    $duration = [int][math]::Floor(24 / $count)
    $start = [int](($StartHour + $duration * $i) % 24)
    $end = [int](($StartHour + $duration * ($i + 1)) % 24)
```

**New approach:** Each item now has `startTime` ("HH:MM"). Parse hour from it. The "end" is the next item's start hour minus 1.

**Step 1: Edit `lib/generate-bat.ps1`** — update `New-TimeVbs` to remove `$StartHour` param and calculate `$start`/`$end` from `$item.startTime` and `$items[$i+1].startTime`:

```powershell
function New-TimeVbs {
    param (
        [array]$Items,
        [string]$OpenRGBPath,
        [bool]$WithRetry = $false
    )

    # ... (keep all the header VBS generation the same) ...

    for ($i = 0; $i -lt $Items.Count; $i++) {
        $item = $Items[$i]
        $prof = $item.profile

        # Parse start hour from "HH:MM"
        $start = [int]($item.startTime -split ":")[0]

        # End = next item's start - 1, or wrap around to last item's start - 1
        if ($i -lt $Items.Count - 1) {
            $end = [int]($Items[$i + 1].startTime -split ":")[0]
        } else {
            # Last item: ends at first item's start
            $end = [int]($Items[0].startTime -split ":")[0]
        }

        # Same Case logic as before using $start and $end
```

Also update the two call sites at bottom of file:
```powershell
# Old:
$autoprofileVbsContent = New-TimeVbs -Items $config.schedules.items -StartHour $config.schedules.startHour -OpenRGBPath $openRGBPath -WithRetry $true
$autorainbowVbsContent = New-TimeVbs -Items $config.rainbow.items -StartHour $config.rainbow.startHour -OpenRGBPath $openRGBPath -WithRetry $false

# New:
$autoprofileVbsContent = New-TimeVbs -Items $config.schedules.items -OpenRGBPath $openRGBPath -WithRetry $true
$autorainbowVbsContent = New-TimeVbs -Items $config.rainbow.items -OpenRGBPath $openRGBPath -WithRetry $false
```

Note: rainbow items don't have `startTime` — add a helper that generates synthetic startTime for rainbow items based on `startHour` before calling:

```powershell
# Before calling for rainbow:
$rainbowStart = [int]$config.rainbow.startHour
$rainbowCount = $config.rainbow.items.Count
$rainbowDuration = [int][math]::Floor(24 / $rainbowCount)
$rainbowItemsWithTime = for ($i = 0; $i -lt $rainbowCount; $i++) {
    $item = $config.rainbow.items[$i]
    $hour = ($rainbowStart + $rainbowDuration * $i) % 24
    [PSCustomObject]@{
        vbsName   = $item.vbsName
        profile   = $item.profile
        startTime = "{0:D2}:00" -f $hour
    }
}
$autorainbowVbsContent = New-TimeVbs -Items $rainbowItemsWithTime -OpenRGBPath $openRGBPath -WithRetry $false
```

**Step 2: Commit**
```bash
git add lib/generate-bat.ps1
git commit -m "feat(lib): generate-bat reads startTime per item, synthesizes times for rainbow"
```

---

### Task 5: Create `gui/runner.py`

**Files:**
- Create: `gui/runner.py`

**What it does:** Invokes `setup.ps1` as Administrator (UAC prompt) and returns success/error message.

**Step 1: Create the file**

```python
# runner.py - Invoke setup.ps1 as Administrator

import subprocess
import os


def run_setup(script_dir: str) -> tuple[bool, str]:
    """Run setup.ps1 as Administrator via PowerShell -Verb RunAs.

    Returns (success: bool, message: str).
    """
    setup_ps1 = os.path.join(script_dir, "setup.ps1")
    if not os.path.isfile(setup_ps1):
        return False, f"setup.ps1 not found: {setup_ps1}"

    # PowerShell Start-Process with RunAs launches UAC prompt
    cmd = [
        "powershell", "-NoProfile", "-Command",
        f'Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"{setup_ps1}`"" -Verb RunAs -Wait'
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            return True, "Setup finished successfully."
        return False, f"Setup failed (exit {result.returncode}): {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return False, "Setup timed out after 120 seconds."
    except Exception as e:
        return False, str(e)
```

**Step 2: Commit**
```bash
git add gui/runner.py
git commit -m "feat(gui): add runner - invoke setup.ps1 as Administrator via UAC"
```

---

### Task 6: Create `gui/__init__.py`

**Files:**
- Create: `gui/__init__.py`

Empty file to make `gui/` a Python package.

```python
```

**Step 1: Create file, commit**
```bash
git add gui/__init__.py
git commit -m "feat(gui): add package __init__"
```

---

### Task 7: Create `gui/gui.py` — Setup Tab

**Files:**
- Create: `gui/gui.py`

Build the main window skeleton + Setup tab first (profile detection). Other tabs in next tasks.

**Step 1: Create `gui/gui.py` with MainWindow and Setup tab**

```python
# gui.py - Auto OpenRGB GUI
# Entry point: python -m gui.gui  (from project root)

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from gui.profile_scanner import scan_profiles
from gui.config_writer import read_config, write_config
from gui.runner import run_setup

# Project root = parent of gui/ folder
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")


class MainWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Auto OpenRGB Setup")
        self.root.resizable(False, False)

        self.profiles: list[str] = []
        self._build_ui()
        self._load_existing_config()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_setup = ttk.Frame(notebook)
        self.tab_schedule = ttk.Frame(notebook)
        self.tab_fkeys = ttk.Frame(notebook)
        self.tab_extras = ttk.Frame(notebook)

        notebook.add(self.tab_setup,    text="Setup")
        notebook.add(self.tab_schedule, text="Raspored")
        notebook.add(self.tab_fkeys,    text="Tastature")
        notebook.add(self.tab_extras,   text="Ekstra")

        self._build_setup_tab()
        self._build_schedule_tab()
        self._build_fkeys_tab()
        self._build_extras_tab()
        self._build_bottom_bar()

    def _build_setup_tab(self):
        f = self.tab_setup

        ttk.Label(f, text="OpenRGB putanja:").grid(row=0, column=0, sticky="w", padx=10, pady=(15, 2))

        self.var_path = tk.StringVar()
        path_entry = ttk.Entry(f, textvariable=self.var_path, width=55)
        path_entry.grid(row=1, column=0, padx=(10, 5), pady=2, sticky="ew")

        ttk.Button(f, text="Browse...", command=self._browse_openrgb).grid(row=1, column=1, padx=(0, 10), pady=2)

        self.lbl_status = ttk.Label(f, text="Status: —")
        self.lbl_status.grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=5)

        ttk.Label(f, text="Pronađeni profili:").grid(row=3, column=0, sticky="w", padx=10, pady=(10, 2))

        self.lbl_profiles = ttk.Label(f, text="(nema)", wraplength=450, justify="left")
        self.lbl_profiles.grid(row=4, column=0, columnspan=2, sticky="w", padx=10, pady=2)

        ttk.Button(f, text="↺ Reskenuj profile", command=self._rescan).grid(
            row=5, column=0, sticky="w", padx=10, pady=10
        )

    # Placeholder build methods — implemented in later tasks
    def _build_schedule_tab(self): pass
    def _build_fkeys_tab(self): pass
    def _build_extras_tab(self): pass

    def _build_bottom_bar(self):
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", padx=10, pady=(0, 10))

        self.lbl_bottom_status = ttk.Label(bar, text="Spreman.")
        self.lbl_bottom_status.pack(side="left")

        ttk.Button(bar, text="▶ Primeni", command=self._apply).pack(side="right")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _browse_openrgb(self):
        path = filedialog.askopenfilename(
            title="Izaberi OpenRGB.exe",
            filetypes=[("OpenRGB executable", "OpenRGB.exe"), ("All files", "*.*")]
        )
        if path:
            self.var_path.set(path.replace("/", "\\"))
            self._rescan()

    def _rescan(self):
        path = self.var_path.get().strip()
        if not os.path.isfile(path):
            self.lbl_status.config(text="Status: ❌ Fajl nije pronađen")
            self.profiles = []
            self.lbl_profiles.config(text="(nema)")
            return

        self.profiles = scan_profiles(path)
        if self.profiles:
            self.lbl_status.config(text=f"Status: ✅ OpenRGB pronađen — {len(self.profiles)} profila")
            self.lbl_profiles.config(text=", ".join(self.profiles))
        else:
            self.lbl_status.config(text="Status: ⚠️ OpenRGB nađen, ali nema .orp profila")
            self.lbl_profiles.config(text="(nema)")
        self._refresh_dropdowns()

    def _refresh_dropdowns(self):
        """Update all dropdowns in other tabs after profile rescan. Implemented in later tasks."""
        pass

    def _load_existing_config(self):
        state = read_config(CONFIG_PATH)
        if not state:
            return
        self.var_path.set(state["openRGBPath"])
        self._rescan()
        # Populate other tabs — called after they are built in later tasks

    def _apply(self):
        if not os.path.isfile(self.var_path.get().strip()):
            messagebox.showerror("Greška", "OpenRGB putanja nije validna.")
            return
        self.lbl_bottom_status.config(text="Pisanje config.json...")
        self.root.update()

        state = self._collect_state()
        write_config(CONFIG_PATH, state)

        self.lbl_bottom_status.config(text="Pokretanje setup.ps1 (Admin)...")
        self.root.update()

        ok, msg = run_setup(SCRIPT_DIR)
        if ok:
            self.lbl_bottom_status.config(text=f"✅ {msg}")
        else:
            self.lbl_bottom_status.config(text=f"❌ {msg}")

    def _collect_state(self) -> dict:
        """Collect current GUI state into dict for config_writer. Extended in later tasks."""
        return {
            "openRGBPath": self.var_path.get().strip(),
            "schedules": [],
            "extras": [],
            "rainbow": [],
        }


def main():
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
```

**Step 2: Test it runs**
```
python -m gui.gui
```
Expected: Window opens with "Setup" tab, browse button works, profile list populates.

**Step 3: Commit**
```bash
git add gui/gui.py
git commit -m "feat(gui): main window skeleton with Setup tab and profile scanning"
```

---

### Task 8: Add Raspored (Schedule) Tab to `gui/gui.py`

**Files:**
- Modify: `gui/gui.py`

**What to build:** Table with rows for each schedule slot. Each row: slot number (label), start time (spinbox HH:MM), end time (read-only label), profile (combobox). Controls: "Početni sat" + "Broj slotova" + "Resetuj" button.

**Step 1: Add schedule tab state variables to `__init__`**

Add after `self.profiles = []`:
```python
self.schedule_rows: list[dict] = []  # each: {"start_var", "end_lbl", "profile_var"}
self.var_slot_count = tk.IntVar(value=8)
self.var_start_hour = tk.IntVar(value=3)
```

**Step 2: Replace `_build_schedule_tab` placeholder**

```python
def _build_schedule_tab(self):
    f = self.tab_schedule

    # Controls row
    ctrl = ttk.Frame(f)
    ctrl.pack(fill="x", padx=10, pady=10)

    ttk.Label(ctrl, text="Početni sat:").pack(side="left")
    ttk.Spinbox(ctrl, from_=0, to=23, width=4, textvariable=self.var_start_hour).pack(side="left", padx=5)

    ttk.Label(ctrl, text="  Broj slotova:").pack(side="left")
    slot_spin = ttk.Spinbox(ctrl, from_=2, to=24, width=4, textvariable=self.var_slot_count)
    slot_spin.pack(side="left", padx=5)
    slot_spin.bind("<FocusOut>", lambda e: self._rebuild_schedule_table())

    ttk.Button(ctrl, text="↺ Resetuj", command=self._reset_schedule).pack(side="left", padx=10)

    # Table header
    hdr = ttk.Frame(f)
    hdr.pack(fill="x", padx=10)
    for text, w in [("Slot", 5), ("Početak", 10), ("Kraj", 10), ("Profil", 25)]:
        ttk.Label(hdr, text=text, width=w, anchor="w").pack(side="left")

    # Scrollable table area
    self.schedule_frame = ttk.Frame(f)
    self.schedule_frame.pack(fill="both", expand=True, padx=10)

    self.lbl_gap_warning = ttk.Label(f, text="", foreground="orange")
    self.lbl_gap_warning.pack(padx=10, anchor="w")

    self._rebuild_schedule_table()

def _rebuild_schedule_table(self, keep_profiles=False):
    """Rebuild schedule rows from current slot count and start hour."""
    # Save current profiles if keeping
    old_profiles = [row["profile_var"].get() for row in self.schedule_rows] if keep_profiles else []

    # Clear existing rows
    for widget in self.schedule_frame.winfo_children():
        widget.destroy()
    self.schedule_rows.clear()

    count = self.var_slot_count.get()
    start = self.var_start_hour.get()
    duration = 24 // count

    for i in range(count):
        hour = (start + duration * i) % 24
        start_time = f"{hour:02d}:00"
        row_frame = ttk.Frame(self.schedule_frame)
        row_frame.pack(fill="x", pady=1)

        ttk.Label(row_frame, text=str(i + 1), width=5).pack(side="left")

        start_var = tk.StringVar(value=start_time)
        start_spin = ttk.Entry(row_frame, textvariable=start_var, width=8)
        start_spin.pack(side="left", padx=2)
        start_spin.bind("<FocusOut>", lambda e: self._update_end_times())

        end_lbl = ttk.Label(row_frame, text="—", width=10)
        end_lbl.pack(side="left", padx=2)

        profile_var = tk.StringVar(value=old_profiles[i] if i < len(old_profiles) else "")
        combo = ttk.Combobox(row_frame, textvariable=profile_var, values=self.profiles, width=22, state="readonly")
        combo.pack(side="left", padx=2)

        self.schedule_rows.append({
            "start_var": start_var,
            "end_lbl": end_lbl,
            "profile_var": profile_var,
        })

    self._update_end_times()

def _update_end_times(self):
    """Recalculate end time labels and check for gaps."""
    rows = self.schedule_rows
    gaps = []
    for i, row in enumerate(rows):
        next_start = rows[(i + 1) % len(rows)]["start_var"].get()
        try:
            nh, nm = map(int, next_start.split(":"))
            end_min = (nh * 60 + nm - 1) % (24 * 60)
            end_str = f"{end_min // 60:02d}:{end_min % 60:02d}"
            row["end_lbl"].config(text=end_str)
        except ValueError:
            row["end_lbl"].config(text="??")

        # Gap detection: end of this row + 1 should equal start of next
        try:
            sh, sm = map(int, row["start_var"].get().split(":"))
            nh2, nm2 = map(int, rows[(i + 1) % len(rows)]["start_var"].get().split(":"))
            this_end_min = (nh2 * 60 + nm2 - 1) % (24 * 60)
            expected_next = (sh * 60 + sm + 24 * 60 // len(rows)) % (24 * 60)
            # Simple gap check: if next start != this end + 1 minute
            actual_next = nh2 * 60 + nm2
            if actual_next != (this_end_min + 1) % (24 * 60):
                gaps.append(i + 1)
        except (ValueError, ZeroDivisionError):
            pass

    if gaps:
        self.lbl_gap_warning.config(text=f"⚠️ Moguće vremenske rupe kod slotova: {gaps}")
    else:
        self.lbl_gap_warning.config(text="")

def _reset_schedule(self):
    self._rebuild_schedule_table(keep_profiles=True)
```

**Step 3: Update `_refresh_dropdowns` to also refresh schedule combos**

```python
def _refresh_dropdowns(self):
    for row in self.schedule_rows:
        # Find combobox in row frame and update values
        pass  # Will be done via rebuild
    self._rebuild_schedule_table(keep_profiles=True)
    self._refresh_fkeys()    # defined in Task 9
    self._refresh_extras()   # defined in Task 10
```

**Step 4: Update `_collect_state` to include schedule data**

```python
def _collect_state(self) -> dict:
    schedules = []
    for i, row in enumerate(self.schedule_rows):
        schedules.append({
            "taskName": f"OpenRGB slot{i+1}",
            "vbsName": f"slot{i+1}",
            "profile": row["profile_var"].get(),
            "startTime": row["start_var"].get(),
        })
    return {
        "openRGBPath": self.var_path.get().strip(),
        "schedules": schedules,
        "extras": [],
        "rainbow": [],
    }
```

**Step 5: Update `_load_existing_config` to populate schedule tab**

In `_load_existing_config`, after `self._rescan()`, add:
```python
if state.get("schedules"):
    self.var_slot_count.set(len(state["schedules"]))
    self._rebuild_schedule_table()
    for i, item in enumerate(state["schedules"]):
        if i < len(self.schedule_rows):
            self.schedule_rows[i]["start_var"].set(item["startTime"])
            self.schedule_rows[i]["profile_var"].set(item["profile"])
    self._update_end_times()
```

**Step 6: Test**
```
python -m gui.gui
```
Expected: Raspored tab shows table with 8 rows, time spinboxes, profile dropdowns.

**Step 7: Commit**
```bash
git add gui/gui.py
git commit -m "feat(gui): add Raspored tab with editable schedule slots and gap detection"
```

---

### Task 9: Add Tastature (F-keys) Tab to `gui/gui.py`

**Files:**
- Modify: `gui/gui.py`

**Step 1: Add F-key state to `__init__`**

```python
self.fkey_vars: list[tk.StringVar] = []  # 12 items, F1-F12
```

**Step 2: Replace `_build_fkeys_tab` placeholder**

```python
def _build_fkeys_tab(self):
    f = self.tab_fkeys
    ttk.Label(f, text="Dodeli profil na F tastere:").pack(anchor="w", padx=10, pady=(15, 5))

    grid = ttk.Frame(f)
    grid.pack(padx=10)

    self.fkey_vars = []
    for i in range(12):
        row, col = divmod(i, 2)  # 2 columns
        var = tk.StringVar()
        self.fkey_vars.append(var)
        ttk.Label(grid, text=f"F{i+1}:", width=5).grid(row=row, column=col*2, sticky="e", padx=5, pady=3)
        ttk.Combobox(grid, textvariable=var, values=self.profiles, width=20, state="readonly").grid(
            row=row, column=col*2+1, sticky="w", padx=5, pady=3
        )

    ttk.Label(f, text="ℹ VBS fajlovi se generišu u rainbow/", foreground="gray").pack(anchor="w", padx=10, pady=10)

def _refresh_fkeys(self):
    for widget in self.tab_fkeys.winfo_children():
        pass  # Comboboxes update their values list via config on the widget
    # Re-set values on all comboboxes in fkeys tab
    for frame in self.tab_fkeys.winfo_children():
        for child in frame.winfo_children() if hasattr(frame, 'winfo_children') else []:
            if isinstance(child, ttk.Combobox):
                child.config(values=self.profiles)
```

**Step 3: Update `_collect_state` to include rainbow/F-key data**

```python
# In _collect_state, replace "rainbow": []
rainbow = []
for i, var in enumerate(self.fkey_vars):
    rainbow.append({"vbsName": f"F{i+1}", "profile": var.get()})
# ... add to return dict
```

**Step 4: Update `_load_existing_config` to populate F-keys**

```python
if state.get("rainbow"):
    for i, item in enumerate(state["rainbow"]):
        if i < len(self.fkey_vars):
            self.fkey_vars[i].set(item["profile"])
```

**Step 5: Test**
```
python -m gui.gui
```
Expected: Tastature tab shows F1-F12 in 2 columns with profile dropdowns.

**Step 6: Commit**
```bash
git add gui/gui.py
git commit -m "feat(gui): add Tastature tab with F1-F12 profile assignment"
```

---

### Task 10: Add Ekstra Tab to `gui/gui.py`

**Files:**
- Modify: `gui/gui.py`

**Step 1: Add extras state**

```python
self.extra_rows: list[dict] = []  # each: {"name_var", "profile_var", "frame"}
```

**Step 2: Replace `_build_extras_tab` placeholder**

```python
def _build_extras_tab(self):
    f = self.tab_extras
    ttk.Label(f, text="Ručni profili (pozivaju se VBS-om):").pack(anchor="w", padx=10, pady=(15, 5))

    self.extras_container = ttk.Frame(f)
    self.extras_container.pack(fill="both", expand=True, padx=10)

    ttk.Button(f, text="+ Dodaj novi", command=self._add_extra_row).pack(anchor="w", padx=10, pady=10)

def _add_extra_row(self, name="", profile=""):
    container = self.extras_container
    row_frame = ttk.Frame(container)
    row_frame.pack(fill="x", pady=2)

    ttk.Label(row_frame, text="Naziv:").pack(side="left")
    name_var = tk.StringVar(value=name)
    ttk.Entry(row_frame, textvariable=name_var, width=12).pack(side="left", padx=5)

    ttk.Label(row_frame, text="Profil:").pack(side="left")
    profile_var = tk.StringVar(value=profile)
    ttk.Combobox(row_frame, textvariable=profile_var, values=self.profiles, width=20, state="readonly").pack(side="left", padx=5)

    row = {"name_var": name_var, "profile_var": profile_var, "frame": row_frame}

    def delete():
        self.extra_rows.remove(row)
        row_frame.destroy()

    ttk.Button(row_frame, text="🗑", width=3, command=delete).pack(side="left", padx=5)
    self.extra_rows.append(row)

def _refresh_extras(self):
    for row in self.extra_rows:
        for child in row["frame"].winfo_children():
            if isinstance(child, ttk.Combobox):
                child.config(values=self.profiles)
```

**Step 3: Update `_collect_state` extras section**

```python
extras = [
    {"vbsName": row["name_var"].get(), "profile": row["profile_var"].get()}
    for row in self.extra_rows
    if row["name_var"].get().strip()
]
```

**Step 4: Update `_load_existing_config` extras**

```python
for item in state.get("extras", []):
    self._add_extra_row(name=item["vbsName"], profile=item["profile"])
```

**Step 5: Test full flow**
```
python -m gui.gui
```
Expected: All 4 tabs work. Fill in values, click Primeni → config.json gets written, UAC prompt appears, setup.ps1 runs.

**Step 6: Final commit**
```bash
git add gui/gui.py
git commit -m "feat(gui): add Ekstra tab - dynamic list of manual profile shortcuts"
```

---

### Task 11: Add `gui/gui.md` documentation

**Files:**
- Create: `gui/gui.md`

Per project Rule #3 (MD-First), scripts need `.md` docs.

```markdown
# GUI Setup Wizard

**Script:** [GUI entry point](gui.py)

## Purpose
Python tkinter GUI for configuring Auto OpenRGB without manually editing config.json.
Detects OpenRGB profiles, configures schedule/F-keys/extras, writes config.json, and
invokes setup.ps1 as Administrator.

## Dependencies
- Python 3.10+
- tkinter (built-in with Python on Windows)

## Usage
Run from project root:
```
python -m gui.gui
```

## Files
- [gui.py](gui.py) — Main window, all tabs
- [profile_scanner.py](profile_scanner.py) — Detects .orp profile files
- [config_writer.py](config_writer.py) — Reads/writes config.json
- [runner.py](runner.py) — Invokes setup.ps1 as Admin
```

**Commit:**
```bash
git add gui/gui.md
git commit -m "docs(gui): add gui.md documentation"
```

---

### Task 12: Add `gui/__index.md` and update `README.md`

**Files:**
- Create: `gui/__index.md`
- Modify: `README.md` (add link to gui/__index.md)

Per Rule #3, new folder needs `__index.md`. Per navigation requirement, README must link to it.

**`gui/__index.md`:**
```markdown
# GUI Folder

## Purpose
Python tkinter GUI application for configuring Auto OpenRGB without editing config.json manually.

## Contents
- [GUI Setup Wizard](gui.md) — Main entry point and tabs
- [profile_scanner.py](profile_scanner.py) — .orp file detection (no separate .md, simple utility)
- [config_writer.py](config_writer.py) — config.json read/write
- [runner.py](runner.py) — Admin PowerShell invocation

## Usage
```
python -m gui.gui
```
```

In `README.md`: find the file structure section and add `gui/` folder entry. Find the navigation/links section and add link to `gui/__index.md`.

**Commit:**
```bash
git add gui/__index.md README.md
git commit -m "docs: add gui/__index.md and update README navigation"
```
