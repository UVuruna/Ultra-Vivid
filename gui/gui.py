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
        self.schedule_rows: list[dict] = []  # each: {"start_var", "end_lbl", "profile_var"}
        self.fkey_vars: list[tk.StringVar] = []  # 12 items, F1-F12
        self.var_slot_count = tk.IntVar(value=8)
        self.var_start_hour = tk.IntVar(value=3)
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

        self.lbl_status = ttk.Label(f, text="Status: -")
        self.lbl_status.grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=5)

        ttk.Label(f, text="Pronadjeni profili:").grid(row=3, column=0, sticky="w", padx=10, pady=(10, 2))

        self.lbl_profiles = ttk.Label(f, text="(nema)", wraplength=450, justify="left")
        self.lbl_profiles.grid(row=4, column=0, columnspan=2, sticky="w", padx=10, pady=2)

        ttk.Button(f, text="Reskenuj profile", command=self._rescan).grid(
            row=5, column=0, sticky="w", padx=10, pady=10
        )

    # Placeholder build methods - implemented in Tasks 8-10
    def _build_schedule_tab(self):
        f = self.tab_schedule

        ctrl = ttk.Frame(f)
        ctrl.pack(fill="x", padx=10, pady=10)

        ttk.Label(ctrl, text="Pocetni sat:").pack(side="left")
        ttk.Spinbox(ctrl, from_=0, to=23, width=4, textvariable=self.var_start_hour).pack(side="left", padx=5)

        ttk.Label(ctrl, text="  Broj slotova:").pack(side="left")
        slot_spin = ttk.Spinbox(ctrl, from_=2, to=24, width=4, textvariable=self.var_slot_count)
        slot_spin.pack(side="left", padx=5)
        slot_spin.bind("<FocusOut>", lambda e: self._rebuild_schedule_table())

        ttk.Button(ctrl, text="Resetuj", command=self._reset_schedule).pack(side="left", padx=10)

        hdr = ttk.Frame(f)
        hdr.pack(fill="x", padx=10)
        for text, w in [("Slot", 5), ("Pocetak", 10), ("Kraj", 10), ("Profil", 25)]:
            ttk.Label(hdr, text=text, width=w, anchor="w").pack(side="left")

        self.schedule_frame = ttk.Frame(f)
        self.schedule_frame.pack(fill="both", expand=True, padx=10)

        self.lbl_gap_warning = ttk.Label(f, text="", foreground="orange")
        self.lbl_gap_warning.pack(padx=10, anchor="w")

        self._rebuild_schedule_table()

    def _rebuild_schedule_table(self, keep_profiles=False):
        """Rebuild schedule rows from current slot count and start hour."""
        old_profiles = [row["profile_var"].get() for row in self.schedule_rows] if keep_profiles else []

        for widget in self.schedule_frame.winfo_children():
            widget.destroy()
        self.schedule_rows.clear()

        count = self.var_slot_count.get()
        start = self.var_start_hour.get()
        duration = 24 // count if count else 3

        for i in range(count):
            hour = (start + duration * i) % 24
            start_time = f"{hour:02d}:00"
            row_frame = ttk.Frame(self.schedule_frame)
            row_frame.pack(fill="x", pady=1)

            ttk.Label(row_frame, text=str(i + 1), width=5).pack(side="left")

            start_var = tk.StringVar(value=start_time)
            start_entry = ttk.Entry(row_frame, textvariable=start_var, width=8)
            start_entry.pack(side="left", padx=2)
            start_entry.bind("<FocusOut>", lambda e: self._update_end_times())

            end_lbl = ttk.Label(row_frame, text="-", width=10)
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
        """Recalculate end time labels."""
        rows = self.schedule_rows
        if not rows:
            return
        for i, row in enumerate(rows):
            next_start = rows[(i + 1) % len(rows)]["start_var"].get()
            try:
                nh, nm = map(int, next_start.split(":"))
                end_min = (nh * 60 + nm - 1) % (24 * 60)
                end_str = f"{end_min // 60:02d}:{end_min % 60:02d}"
                row["end_lbl"].config(text=end_str)
            except ValueError:
                row["end_lbl"].config(text="??")

        self.lbl_gap_warning.config(text="")

    def _reset_schedule(self):
        self._rebuild_schedule_table(keep_profiles=True)

    def _build_fkeys_tab(self):
        f = self.tab_fkeys
        ttk.Label(f, text="Dodeli profil na F tastere:").pack(anchor="w", padx=10, pady=(15, 5))

        grid = ttk.Frame(f)
        grid.pack(padx=10)

        self.fkey_vars = []
        for i in range(12):
            row, col = divmod(i, 2)  # 2 columns: F1,F2 in row 0, F3,F4 in row 1, etc.
            var = tk.StringVar()
            self.fkey_vars.append(var)
            ttk.Label(grid, text=f"F{i + 1}:", width=5).grid(row=row, column=col * 2, sticky="e", padx=5, pady=3)
            ttk.Combobox(grid, textvariable=var, values=self.profiles, width=20, state="readonly").grid(
                row=row, column=col * 2 + 1, sticky="w", padx=5, pady=3
            )

        ttk.Label(f, text="VBS fajlovi se generisu u rainbow/", foreground="gray").pack(anchor="w", padx=10, pady=10)

    def _build_extras_tab(self): pass

    def _build_bottom_bar(self):
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", padx=10, pady=(0, 10))

        self.lbl_bottom_status = ttk.Label(bar, text="Spreman.")
        self.lbl_bottom_status.pack(side="left")

        ttk.Button(bar, text="Primeni", command=self._apply).pack(side="right")

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
            self.lbl_status.config(text="Status: Fajl nije pronadjen")
            self.profiles = []
            self.lbl_profiles.config(text="(nema)")
            return

        self.profiles = scan_profiles(path)
        if self.profiles:
            self.lbl_status.config(text=f"Status: OpenRGB pronadjen - {len(self.profiles)} profila")
            self.lbl_profiles.config(text=", ".join(self.profiles))
        else:
            self.lbl_status.config(text="Status: OpenRGB nadjen, ali nema .orp profila")
            self.lbl_profiles.config(text="(nema)")
        self._refresh_dropdowns()

    def _refresh_dropdowns(self):
        """Update all dropdowns in other tabs after profile rescan."""
        self._rebuild_schedule_table(keep_profiles=True)
        self._refresh_fkeys()
        self._refresh_extras()

    def _refresh_fkeys(self):
        """Update F-key combobox values after profile rescan."""
        for widget in self._get_fkey_comboboxes():
            widget.config(values=self.profiles)

    def _get_fkey_comboboxes(self) -> list:
        """Return all Combobox widgets from the fkeys tab grid."""
        result = []
        for frame in self.tab_fkeys.winfo_children():
            if isinstance(frame, ttk.Frame):
                for child in frame.winfo_children():
                    if isinstance(child, ttk.Combobox):
                        result.append(child)
        return result

    def _refresh_extras(self): pass  # implemented in Task 10

    def _load_existing_config(self):
        state = read_config(CONFIG_PATH)
        if not state:
            return
        self.var_path.set(state["openRGBPath"])
        self._rescan()
        if state.get("schedules"):
            self.var_slot_count.set(len(state["schedules"]))
            self._rebuild_schedule_table()
            for i, item in enumerate(state["schedules"]):
                if i < len(self.schedule_rows):
                    self.schedule_rows[i]["start_var"].set(item["startTime"])
                    self.schedule_rows[i]["profile_var"].set(item["profile"])
            self._update_end_times()
        if state.get("rainbow"):
            for i, item in enumerate(state["rainbow"]):
                if i < len(self.fkey_vars):
                    self.fkey_vars[i].set(item["profile"])

    def _apply(self):
        if not os.path.isfile(self.var_path.get().strip()):
            messagebox.showerror("Greska", "OpenRGB putanja nije validna.")
            return
        self.lbl_bottom_status.config(text="Pisanje config.json...")
        self.root.update()

        state = self._collect_state()
        write_config(CONFIG_PATH, state)

        self.lbl_bottom_status.config(text="Pokretanje setup.ps1 (Admin)...")
        self.root.update()

        ok, msg = run_setup(SCRIPT_DIR)
        if ok:
            self.lbl_bottom_status.config(text=f"OK - {msg}")
        else:
            self.lbl_bottom_status.config(text=f"Greska - {msg}")

    def _collect_state(self) -> dict:
        """Collect current GUI state into dict for config_writer."""
        schedules = []
        for i, row in enumerate(self.schedule_rows):
            schedules.append({
                "taskName": f"OpenRGB slot{i + 1}",
                "vbsName": f"slot{i + 1}",
                "profile": row["profile_var"].get(),
                "startTime": row["start_var"].get(),
            })
        rainbow = [
            {"vbsName": f"F{i + 1}", "profile": var.get()}
            for i, var in enumerate(self.fkey_vars)
        ]
        return {
            "openRGBPath": self.var_path.get().strip(),
            "schedules": schedules,
            "extras": [],
            "rainbow": rainbow,
        }


def main():
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
