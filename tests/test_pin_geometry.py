from PySide6.QtCore import QRect

from gaming_buddy.pin import fit_geometry_to_screens, snap_geometry_to_screen_edges


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


def test_geometry_snaps_to_nearby_corner_without_changing_size():
    screen = QRect(0, 0, 1920, 1040)
    requested = QRect(12, 14, 320, 220)

    snapped = snap_geometry_to_screen_edges(requested, [screen])

    assert snapped == QRect(0, 0, 320, 220)


def test_geometry_snaps_to_right_and_bottom_edges():
    screen = QRect(0, 0, 1920, 1040)
    requested = QRect(1590, 810, 320, 220)

    snapped = snap_geometry_to_screen_edges(requested, [screen])

    assert snapped == QRect(1600, 820, 320, 220)


def test_geometry_outside_snap_threshold_is_unchanged():
    screen = QRect(0, 0, 1920, 1040)
    requested = QRect(60, 70, 320, 220)

    assert snap_geometry_to_screen_edges(requested, [screen]) == requested


def test_geometry_snaps_against_the_screen_with_greatest_overlap():
    primary = QRect(0, 0, 1920, 1040)
    secondary = QRect(1920, 0, 2560, 1400)
    requested = QRect(1932, 200, 400, 240)

    snapped = snap_geometry_to_screen_edges(requested, [primary, secondary])

    assert snapped == QRect(1920, 200, 400, 240)
