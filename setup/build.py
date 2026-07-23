"""
Build UltraVivid into a distributable package.

Steps:
  1. Generate ICO from assets/logo.svg (skipped gracefully if SVG missing)
  2. Run PyInstaller (--onedir mode) to create the exe
  3. Sign the exe with self-signed certificate (optional)
  4. Call NSIS to create the installer

Prerequisites:
  - pip install -r requirements.txt
  - Run create_cert.py once (for code signing, optional)
  - Install NSIS (https://nsis.sourceforge.io/) and add to PATH

Usage:
    python setup/build.py
"""

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# -- Paths ---------------------------------------------------------
SETUP_DIR = Path(__file__).parent
PROJECT_DIR = SETUP_DIR.parent
DIST_DIR = PROJECT_DIR / "dist"
BUILD_DIR = PROJECT_DIR / "build"

SVG_PATH = PROJECT_DIR / "assets" / "logo.svg"
ICO_PATH = PROJECT_DIR / "assets" / "UltraVivid.ico"
CERT_PATH = SETUP_DIR / "cert" / "UltraVivid.pfx"
PASSWORD_PATH = SETUP_DIR / "cert" / "password.txt"
NSI_PATH = SETUP_DIR / "installer.nsi"
COMPANY_JSON_PATH = PROJECT_DIR.parent.parent / "company.json"   # monorepo root
VERSION_INFO_PATH = SETUP_DIR / "version_info.txt"               # generated (gitignored)

APP_DESCRIPTION = "Ultra Vivid — rule-based RGB scheduling for OpenRGB devices"


def _read_version() -> str:
    version_file = PROJECT_DIR / "version.py"
    text = version_file.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\'](.+?)["\']', text)
    if not match:
        raise RuntimeError(f"Could not read version from {version_file}")
    return match.group(1)


def _load_password() -> str | None:
    if not PASSWORD_PATH.exists():
        return None
    return PASSWORD_PATH.read_text(encoding="utf-8").strip()


def _load_company() -> dict:
    return json.loads(COMPANY_JSON_PATH.read_text(encoding="utf-8"))


APP_VERSION = _read_version()
CERT_PASSWORD = _load_password()
COMPANY = _load_company()
APP_NAME = "UltraVivid"
ENTRY_POINT = PROJECT_DIR / "main.py"          # single-exe dispatch entry


def step(msg: str):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def run(cmd: list[str], **kwargs):
    """Run a command, print it, and check for errors."""
    print(f"  > {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"  FAILED (exit code {result.returncode})")
        if result.stderr:
            print(f"  {result.stderr}")
        sys.exit(1)
    return result


def _version_tuple(version: str) -> tuple[int, int, int, int]:
    nums = [int(p) for p in version.split(".")]
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums[:4])


def generate_version_info():
    """Write the PyInstaller version-resource file so the exe carries
    CompanyName/ProductName/version in its Windows PE metadata (root pipeline
    Step 2). Without it the exe reports an empty CompanyName — e.g. Vitals'
    company legend lists it as "Unknown"."""
    step("0/4  Generating version_info.txt (CompanyName, version)")
    v = APP_VERSION
    vt = _version_tuple(v)
    content = f"""\
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={vt},
    prodvers={vt},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
    ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'{COMPANY["company_name"]}'),
         StringStruct(u'FileDescription', u'{APP_DESCRIPTION}'),
         StringStruct(u'FileVersion', u'{v}'),
         StringStruct(u'InternalName', u'{APP_NAME}'),
         StringStruct(u'LegalCopyright', u'{COMPANY["copyright_string"]}'),
         StringStruct(u'OriginalFilename', u'{APP_NAME}.exe'),
         StringStruct(u'ProductName', u'{APP_NAME}'),
         StringStruct(u'ProductVersion', u'{v}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [0x0409, 1200])])
  ]
)
"""
    VERSION_INFO_PATH.write_text(content, encoding="utf-8")
    print(f"  Written: {VERSION_INFO_PATH}")
    print(f"  Version: {v}  Company: {COMPANY['company_name']}")


def generate_ico():
    step("1/4  Generating ICO from SVG")

    if not SVG_PATH.exists():
        print(f"  WARNING: SVG not found: {SVG_PATH}")
        print("  Place logo.svg in assets/ to generate the icon.")
        print("  Skipping ICO generation...")
        return

    run([sys.executable, str(SETUP_DIR / "svg_to_ico.py")])


def build_pyinstaller():
    step("2/4  Building exe with PyInstaller")

    # Clean previous build
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            print(f"  Cleaning {d}")
            shutil.rmtree(d)

    # Packages not used at runtime
    exclude_modules = [
        "numpy",
        "setuptools",
        "pkg_resources",
        "charset_normalizer",
        "unittest",
        "xmlrpc",
        "pydoc",
        "tkinter",
        # QWebEngine = Chromium (~500 MB), not needed
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebChannel",
        "PySide6.QtWebEngineQuick",
    ]

    # Modules reached only through lazy/dispatch imports (main.py) or via
    # data-only packages PyInstaller's static scan can miss.
    hidden_imports = [
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtSvg",
        # single-exe dispatch targets (imported inside functions)
        "resolver",
        "hotkey_daemon",
        "gui.app",
        "core.tasks",
        "core.chroma",
        "core.updates",
        "version",          # app_version() reads __version__ at runtime
    ]

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--name", APP_NAME,
        "--windowed",
        "--version-file", str(VERSION_INFO_PATH),
    ]

    # Add icon if it exists
    if ICO_PATH.exists():
        cmd.extend(["--icon", str(ICO_PATH)])
    else:
        print("  NOTE: UltraVivid.ico not found — building without icon.")

    # Bundle read-only resources the app reads at runtime.
    assets_dir = PROJECT_DIR / "assets"
    if assets_dir.exists():
        cmd.extend(["--add-data", f"{assets_dir};assets"])
    world_db = PROJECT_DIR / "data" / "world_locations.json"
    if world_db.exists():
        cmd.extend(["--add-data", f"{world_db};data"])
    default_config = PROJECT_DIR / "config.json"
    if default_config.exists():
        cmd.extend(["--add-data", f"{default_config};."])

    # zoneinfo needs the tzdata package bundled (astral / daylight).
    cmd.extend(["--collect-data", "tzdata"])

    # Add hidden imports
    for mod in hidden_imports:
        cmd.extend(["--hidden-import", mod])

    # Add exclude flags
    for mod in exclude_modules:
        cmd.extend(["--exclude-module", mod])

    # Entry point (must be last)
    cmd.append(str(ENTRY_POINT))

    start = time.time()
    run(cmd)
    elapsed = time.time() - start
    print(f"  PyInstaller completed in {elapsed:.1f}s")

    exe_path = DIST_DIR / APP_NAME / f"{APP_NAME}.exe"
    if not exe_path.exists():
        print(f"  ERROR: Expected exe not found: {exe_path}")
        sys.exit(1)

    # Copy ICO to dist so NSIS shortcuts can reference $INSTDIR\UltraVivid.ico
    if ICO_PATH.exists():
        dist_ico = DIST_DIR / APP_NAME / ICO_PATH.name
        shutil.copy2(ICO_PATH, dist_ico)
        print(f"  Copied {ICO_PATH.name} to {dist_ico.parent}")

    print(f"  Output: {exe_path}")
    return exe_path


def _find_signtool() -> str | None:
    """Locate signtool.exe (PATH first, then the Windows SDK)."""
    signtool = shutil.which("signtool")
    if signtool:
        return signtool
    sdk_paths = [
        Path(r"C:\Program Files (x86)\Windows Kits\10\bin"),
        Path(r"C:\Program Files\Windows Kits\10\bin"),
    ]
    for sdk_base in sdk_paths:
        if sdk_base.exists():
            versions = sorted(sdk_base.glob("10.*/x64/signtool.exe"))
            if versions:
                return str(versions[-1])
    return None


def sign_file(path: Path, what: str) -> bool:
    """Authenticode-sign one file with the project certificate.

    Reused for BOTH the inner exe AND the distributed installer — signing
    only the inner exe leaves the file the user actually runs (the installer)
    unsigned, which defeats the SmartScreen mitigation. Returns True when the
    file was signed, False when a prerequisite was missing (skipped, not an
    error — signing is the documented-optional step).
    """
    if not CERT_PATH.exists():
        print(f"  WARNING: Certificate not found: {CERT_PATH}")
        print("  Run 'python setup/create_cert.py' first — skipping signing.")
        return False
    if not CERT_PASSWORD:
        print("  WARNING: Password file not found — skipping signing.")
        return False
    signtool = _find_signtool()
    if not signtool:
        print("  WARNING: signtool.exe not found (install Windows SDK) — "
              "skipping signing.")
        return False

    run([
        signtool, "sign",
        "/f", str(CERT_PATH),
        "/p", CERT_PASSWORD,
        "/fd", "SHA256",
        "/t", "http://timestamp.digicert.com",
        str(path),
    ])
    print(f"  Signed {what}: {path.name}")
    return True


def sign_exe(exe_path: Path):
    step("3/4  Signing exe with certificate")
    sign_file(exe_path, "exe")


def build_installer():
    step("4/4  Building installer with NSIS")

    makensis = shutil.which("makensis")
    if not makensis:
        # Try common NSIS locations
        nsis_paths = [
            Path(r"C:\Program Files (x86)\NSIS\makensis.exe"),
            Path(r"C:\Program Files\NSIS\makensis.exe"),
        ]
        for p in nsis_paths:
            if p.exists():
                makensis = str(p)
                break

    if not makensis:
        print("  ERROR: makensis.exe not found.")
        print("  Install NSIS from https://nsis.sourceforge.io/")
        sys.exit(1)

    cmd = [
        makensis,
        f"/DPROJECT_DIR={PROJECT_DIR}",
        f"/DDIST_DIR={DIST_DIR}",
        f"/DSETUP_DIR={SETUP_DIR}",
        f"/DAPP_VERSION={APP_VERSION}",
        str(NSI_PATH),
    ]

    run(cmd)

    installer_path = DIST_DIR / f"{APP_NAME}_Setup.exe"
    if installer_path.exists():
        # Sign the installer itself — this is the file the user downloads and
        # runs, so it (not just the inner exe) must carry the signature.
        sign_file(installer_path, "installer")
        print(f"  Installer: {installer_path}")
        size_mb = installer_path.stat().st_size / (1024 * 1024)
        print(f"  Size: {size_mb:.1f} MB")
    else:
        print("  WARNING: Installer exe not found at expected location.")


def _powershell(script: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True, text=True)
    return result.stdout.strip()


def verify_build(exe_path: Path, installer_path: Path):
    """Fail-closed gate: assert the OUTPUT actually carries what the pipeline
    promises, instead of trusting that every step ran. A missing step here
    (no CompanyName, unsigned installer) produces no error on its own — it
    just ships broken metadata — so nothing but an explicit check catches it.

    Asserts: exe CompanyName == company.json, exe FileVersion == version.py,
    and (when a signing cert is configured) both exe AND installer are signed.
    """
    step("VERIFY  metadata + signatures (build fails if anything is missing)")
    problems = []

    info = _powershell(
        f"$v=(Get-Item '{exe_path}').VersionInfo; "
        f"\"$($v.CompanyName)|$($v.FileVersion)\"")
    company, _, file_version = info.partition("|")
    expected_company = COMPANY["company_name"]
    if company != expected_company:
        problems.append(
            f"exe CompanyName is {company!r}, expected {expected_company!r} "
            "(version resource missing/empty — company legends show 'Unknown')")
    if APP_VERSION not in file_version:
        problems.append(
            f"exe FileVersion is {file_version!r}, expected to contain {APP_VERSION!r}")

    # Signing is documented-optional: only assert it when a cert is configured.
    if CERT_PATH.exists() and CERT_PASSWORD:
        for label, target in (("exe", exe_path), ("installer", installer_path)):
            status = _powershell(f"(Get-AuthenticodeSignature '{target}').Status")
            if status in ("", "NotSigned"):
                problems.append(f"{label} is NOT signed (status {status or 'missing'!r})")

    if problems:
        for p in problems:
            print(f"  FAIL: {p}")
        print("\n  Build produced artifacts but they FAIL the pipeline contract.")
        sys.exit(1)

    print(f"  OK: CompanyName={company!r}  FileVersion={file_version!r}")
    if CERT_PATH.exists() and CERT_PASSWORD:
        print("  OK: exe + installer signed")
    else:
        print("  NOTE: signing skipped (no certificate) — installer is UNSIGNED")


def main():
    print(f"Building {APP_NAME} v{APP_VERSION}")
    print(f"Project: {PROJECT_DIR}")

    if not ENTRY_POINT.exists():
        print(f"ERROR: Entry point not found: {ENTRY_POINT}")
        sys.exit(1)

    generate_version_info()
    generate_ico()
    exe_path = build_pyinstaller()
    sign_exe(exe_path)
    build_installer()
    verify_build(exe_path, DIST_DIR / f"{APP_NAME}_Setup.exe")

    step("BUILD COMPLETE")
    print(f"  Installer: {DIST_DIR / f'{APP_NAME}_Setup.exe'}")
    print()


if __name__ == "__main__":
    main()
