from PySide6.QtCore import QRect

from gaming_buddy.pin import fit_geometry_to_screens


def test_geometry_stays_on_its_existing_screen():
    primary = QRect(0, 0, 1920, 1040)
    secondary = QRect(1920, 0, 2560, 1400)
    requested = QRect(2200, 150, 500, 300)

    assert fit_geometry_to_screens(requested, [primary, secondary], primary) == requested


def test_geometry_returns_to_primary_after_monitor_disconnect():
    primary = QRect(0, 0, 1920, 1040)
    requested = QRect(2500, 200, 500, 300)

    restored = fit_geometry_to_screens(requested, [primary], primary)

    assert restored == QRect(1420, 200, 500, 300)


def test_geometry_is_clamped_inside_available_area():
    screen = QRect(0, 0, 1280, 680)
    requested = QRect(-80, -40, 1600, 900)

    restored = fit_geometry_to_screens(requested, [screen], screen)

    assert restored == screen


def test_geometry_is_unchanged_when_screen_information_is_unavailable():
    requested = QRect(40, 50, 300, 200)

    assert fit_geometry_to_screens(requested, []) == requested
