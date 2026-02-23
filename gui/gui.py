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

        self.lbl_status = ttk.Label(f, text="Status: -")
        self.lbl_status.grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=5)

        ttk.Label(f, text="Pronadjeni profili:").grid(row=3, column=0, sticky="w", padx=10, pady=(10, 2))

        self.lbl_profiles = ttk.Label(f, text="(nema)", wraplength=450, justify="left")
        self.lbl_profiles.grid(row=4, column=0, columnspan=2, sticky="w", padx=10, pady=2)

        ttk.Button(f, text="Reskenuj profile", command=self._rescan).grid(
            row=5, column=0, sticky="w", padx=10, pady=10
        )

    # Placeholder build methods - implemented in Tasks 8-10
    def _build_schedule_tab(self): pass
    def _build_fkeys_tab(self): pass
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
        """Update all dropdowns in other tabs after profile rescan. Implemented in Tasks 8-10."""
        pass

    def _load_existing_config(self):
        state = read_config(CONFIG_PATH)
        if not state:
            return
        self.var_path.set(state["openRGBPath"])
        self._rescan()
        # Populate other tabs - done in Tasks 8-10

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
        """Collect current GUI state. Extended in Tasks 8-10."""
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
