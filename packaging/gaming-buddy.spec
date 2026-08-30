from pathlib import Path

import PySide6

PROJECT_ROOT = Path(SPEC).resolve().parent.parent
SOURCE_ROOT = PROJECT_ROOT / "src"
PACKAGE_ROOT = SOURCE_ROOT / "gaming_buddy"
ASSET_ROOT = PACKAGE_ROOT / "assets"
PYSIDE_ROOT = Path(PySide6.__file__).resolve().parent
WINDOWS_RUNTIME_NAMES = (
    "MSVCP140.dll",
    "MSVCP140_1.dll",
    "MSVCP140_2.dll",
    "VCRUNTIME140.dll",
    "VCRUNTIME140_1.dll",
)


analysis = Analysis(
    [str(PACKAGE_ROOT / "__main__.py")],
    pathex=[str(SOURCE_ROOT)],
    binaries=[(str(PYSIDE_ROOT / name), ".") for name in WINDOWS_RUNTIME_NAMES],
    datas=[(str(ASSET_ROOT), "gaming_buddy/assets")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Qt uses the Windows system ICU shim. A same-named ICU binary found on a build
# machine's PATH is incompatible because its public symbols are version-suffixed.
analysis.binaries = [
    entry
    for entry in analysis.binaries
    if Path(entry[0]).name.casefold() not in {"icuuc.dll", "icudt78.dll"}
]

python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="GamingBuddy",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ASSET_ROOT / "app-icon.ico"),
    version=str(PROJECT_ROOT / "packaging" / "version_info.txt"),
)

bundle = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="GamingBuddy",
)
