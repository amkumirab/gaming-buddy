import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QImage, QPixmap

from gaming_buddy import capture


class Screen:
    def __init__(self, geometry, image):
        self.area = geometry
        self.image = image

    def geometry(self):
        return QRect(self.area)

    def grabWindow(self, _):
        return QPixmap.fromImage(self.image)


def test_region_capture_rejects_a_failed_monitor_instead_of_saving_transparent_pixels(
    qt_application, monkeypatch,
):
    good = QImage(100, 100, QImage.Format.Format_RGB32)
    screens = [Screen(QRect(-100, 0, 100, 100), good), Screen(QRect(0, 0, 100, 100), QImage())]
    monkeypatch.setattr(capture.QGuiApplication, "screens", lambda: screens)
    with pytest.raises(RuntimeError, match="could not be captured"):
        capture.grab_virtual_desktop()


def test_region_capture_rejects_a_display_removed_during_snapshot(qt_application, monkeypatch):
    image = QImage(100, 100, QImage.Format.Format_RGB32)
    monkeypatch.setattr(capture.QGuiApplication, "screens", lambda: [Screen(QRect(), image)])
    with pytest.raises(RuntimeError, match="display layout changed"):
        capture.grab_virtual_desktop()


def test_valid_negative_coordinates_and_fractional_dpi_keep_native_pixels(qt_application, monkeypatch):
    image = QImage(150, 125, QImage.Format.Format_RGB32)
    image.fill(0xff123456)
    monkeypatch.setattr(capture.QGuiApplication, "screens",
                        lambda: [Screen(QRect(-120, -100, 120, 100), image)])
    snapshot = capture.grab_virtual_desktop()
    result = snapshot.crop_native(QRect(-112, -92, 80, 40))
    assert (result.width(), result.height()) == (100, 50)
    assert result.pixelColor(10, 10).name() == "#123456"
