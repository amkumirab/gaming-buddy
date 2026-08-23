from PySide6.QtCore import QCoreApplication, QSettings

from gaming_buddy.profiles import (
    ActiveApplication,
    ActiveGameDetector,
    GameProfileStore,
    belongs_to_profile,
    normalize_executable,
)


def test_executable_names_are_normalized():
    assert normalize_executable(r"C:\Games\Control\Control_DX12.EXE") == "control_dx12.exe"
    assert normalize_executable("  eldenring.exe  ") == "eldenring.exe"


def test_profile_workspace_includes_general_cards():
    assert belongs_to_profile("Control", "control")
    assert belongs_to_profile("General", "Control")
    assert belongs_to_profile("", "Control")
    assert not belongs_to_profile("Elden Ring", "Control")


def test_game_profiles_persist_and_can_be_replaced(tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    profiles = GameProfileStore(settings)
    profiles.link(r"C:\Games\CONTROL_DX12.EXE", "Control")
    profiles.link("eldenring.exe", "Elden Ring")

    reopened = GameProfileStore(settings)
    assert reopened.game_for("control_dx12.exe") == "Control"
    assert reopened.game_for(r"D:\Steam\ELDENRING.EXE") == "Elden Ring"

    reopened.replace({"alanwake2.exe": "Alan Wake 2"})
    assert reopened.all() == {"alanwake2.exe": "Alan Wake 2"}
    assert GameProfileStore(settings).game_for("control_dx12.exe") is None


def test_detector_tracks_only_external_applications():
    QCoreApplication.instance() or QCoreApplication([])
    applications = iter(
        (
            ActiveApplication("gaming-buddy.exe", "Gaming Buddy", 10),
            ActiveApplication("explorer.exe", "Desktop", 20),
            ActiveApplication("Control_DX12.EXE", "Control", 30),
            ActiveApplication("control_dx12.exe", "Control", 30),
            ActiveApplication("browser.exe", "Browser", 40),
        )
    )
    detector = ActiveGameDetector(reader=lambda: next(applications), own_process_id=10)
    detected: list[ActiveApplication] = []
    detector.active_changed.connect(detected.append)

    for _ in range(5):
        detector.poll_now()

    assert [application.executable for application in detected] == [
        "control_dx12.exe",
        "browser.exe",
    ]
    assert detector.last_external_application == ActiveApplication("browser.exe", "Browser", 40)
