# runner.py - Invoke setup.ps1 as Administrator

import subprocess
import os


def run_setup(script_dir: str) -> tuple[bool, str]:
    """Run setup.ps1 as Administrator via PowerShell -Verb RunAs.

    Returns (success: bool, message: str).
    Raises no exceptions - all errors returned as (False, message).
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
