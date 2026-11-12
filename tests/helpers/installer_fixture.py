"""Compile the production installer logic against disposable, versioned fixture payloads."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP_ID = "57C1EB82-EEAD-4E5F-8F24-49C61A578D08"


def compiler_path() -> Path | None:
    found = shutil.which("ISCC.exe")
    candidates = ([Path(found)] if found else []) + [
        Path(os.environ.get(key, "")) / suffix / "ISCC.exe"
        for key, suffix in (("LOCALAPPDATA", "Programs/Inno Setup 6"),
                            ("ProgramFiles(x86)", "Inno Setup 6"),
                            ("ProgramFiles", "Inno Setup 6"))
    ]
    return next((path for path in candidates if path.is_file()), None)


class InstallerFixture:
    def __init__(self, root: Path, compiler: Path):
        self.root = root.resolve()
        self.compiler = compiler
        self.guid = str(uuid.uuid4()).upper()
        self.install = self.root / "program"
        self.data = self.root / "data"
        self.app_mutex = rf"Local\GamingBuddy.App.{self.guid}"
        self.setup_mutex = rf"Local\GamingBuddy.Setup.{self.guid}"
        self.key = ("Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\"
                    f"{{{self.guid}}}_is1")
        self.settings_key = rf"Software\GamingBuddyInstallerTests\{self.guid}"
        self._setups: dict[str, Path] = {}
        self._uninstalled = False
        maintenance = (ROOT / "packaging/installer-maintenance.iss").read_text(encoding="utf-8")
        assert APP_ID in maintenance and self.guid != APP_ID
        (self.root / "installer-maintenance.iss").write_text(
            maintenance.replace(APP_ID, self.guid), encoding="utf-8",
        )

    def setup(self, version: str) -> Path:
        if version in self._setups:
            return self._setups[version]
        payload = self.root / f"payload-{version}"
        payload.mkdir()
        (payload / "_internal").mkdir()
        (payload / "_internal/runtime.txt").write_text(f"Fixture runtime {version}")
        source = payload / "fixture.cs"
        source.write_text(
            'using System; using System.Threading; using System.IO; using System.Reflection;\n'
            f'[assembly: AssemblyFileVersion("{version}.0")]\n'
            'class Fixture { static void Main(string[] args) { if (args.Length != 2) return;\n'
            f'using (var mutex = new Mutex(false, @"{self.app_mutex}")) {{\n'
            'File.WriteAllText(args[0], "ready");\n'
            'while (!File.Exists(args[1])) Thread.Sleep(20);\n'
            '} } }', encoding="utf-8",
        )
        csc = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        result = subprocess.run([str(csc), "/nologo", "/target:winexe",
                                 f"/out:{payload / 'GamingBuddy.exe'}", str(source)],
                                check=False, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        source.unlink()
        text = (ROOT / "packaging/gaming-buddy.iss").read_text(encoding="utf-8")
        assert text.count(APP_ID) >= 3
        text = text.replace(APP_ID, self.guid)
        assert "AppId={{" + self.guid + "}" in text
        text = text.replace('#define MyAppName "Gaming Buddy"',
                            '#define MyAppName "Gaming Buddy installer fixture"')
        text = re.sub(r'#define MyAppVersion "[^"]+"', f'#define MyAppVersion "{version}"', text)
        text = re.sub(r'^VersionInfoVersion=.*$', f'VersionInfoVersion={version}.0', text,
                      flags=re.MULTILINE)
        replacements = {
            r"{localappdata}\Programs\Gaming Buddy": str(self.install),
            r"{localappdata}\GamingBuddy": str(self.data),
            r"Software\GamingBuddy": self.settings_key,
            'ValueName: "GamingBuddy"': f'ValueName: "GBFixture-{self.guid}"',
            r"{autoprograms}": str(self.root / "shortcuts"),
            r"{autodesktop}": str(self.root / "desktop"),
            r"..\dist\GamingBuddy": str(payload),
            r"..\src\gaming_buddy\assets\app-icon.ico": str(ROOT / "src/gaming_buddy/assets/app-icon.ico"),
            r"..\LICENSE": str(ROOT / "LICENSE"),
            "OutputDir=..\\release": f"OutputDir={self.root / version}",
        }
        for old, new in replacements.items():
            assert old in text, old
            text = text.replace(old, new)
        # Only the fixture identity, payload and destinations differ; maintenance code is unchanged.
        script = self.root / f"fixture-{version}.iss"
        script.write_text(text, encoding="utf-8")
        result = subprocess.run([str(self.compiler), "/Q", str(script)], capture_output=True,
                                check=False, text=True, timeout=45)
        assert result.returncode == 0, result.stdout + result.stderr
        setup = self.root / version / f"Gaming-Buddy-Setup-{version}-x64.exe"
        assert setup.is_file()
        self._setups[version] = setup
        return setup

    def run(self, executable: Path) -> subprocess.CompletedProcess:
        return subprocess.run([str(executable), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/SP-",
                               "/NORESTART", f"/LOG={self.root / 'last-setup.log'}"],
                              check=False, capture_output=True, text=True, timeout=45)

    def uninstall(self):
        uninstaller = self.install / "unins000.exe"
        if uninstaller.exists() and not self._uninstalled:
            result = self.run(uninstaller)
            assert result.returncode == 0, (self.root / "last-setup.log").read_text(errors="replace")
            self._uninstalled = True

    def cleanup(self):
        import winreg

        self.uninstall()
        for key in (self.key, self.settings_key):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, key, view)
                except FileNotFoundError:
                    pass
