"""Ultra Vivid single entry point — one executable, three roles.

Frozen as one exe (PyInstaller), the same binary is the GUI, the
scheduled-tick resolver, and the resident daemon; the scheduled tasks
and Synapse slots invoke it with a flag. Dispatch by first argument:

    UltraVivid.exe                 -> GUI (config editor)
    UltraVivid.exe --daemon        -> hotkey + Chroma daemon
    UltraVivid.exe --install-tasks -> register scheduled tasks (UAC)
    UltraVivid.exe --tick|--color|--shortcut|--off|--dry-run|
                   --write-slots|--list-devices|--force   -> resolver

From the repo, resolver.py / hotkey_daemon.py / gui/app.py can still be
run directly; this launcher just unifies them for the packaged build.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

_RESOLVER_FLAGS = {
    "--tick", "--color", "--shortcut", "--off", "--dry-run",
    "--write-slots", "--list-devices", "--force",
}


def main() -> None:
    args = sys.argv[1:]

    if "--daemon" in args:
        from hotkey_daemon import main as daemon_main
        daemon_main()
    elif "--install-tasks" in args:
        from core import tasks
        tasks.install(elevated="--elevated" in args)
    elif any(a in _RESOLVER_FLAGS for a in args):
        # Strip the launcher-only marker so resolver's argparse is happy.
        sys.argv = [sys.argv[0]] + [a for a in args if a != "--tick"]
        from resolver import main as resolver_main
        resolver_main()
    else:
        from gui.app import main as gui_main
        gui_main()


if __name__ == "__main__":
    main()
