from pathlib import Path

PROJECT_ROOT = Path(SPEC).resolve().parent.parent
SOURCE_ROOT = PROJECT_ROOT / "src"
PACKAGE_ROOT = SOURCE_ROOT / "gaming_buddy"
ASSET_ROOT = PACKAGE_ROOT / "assets"


analysis = Analysis(
    [str(PACKAGE_ROOT / "__main__.py")],
    pathex=[str(SOURCE_ROOT)],
    binaries=[],
    datas=[(str(ASSET_ROOT), "gaming_buddy/assets")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

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
