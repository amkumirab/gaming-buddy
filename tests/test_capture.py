import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from gaming_buddy.capture import DesktopSnapshot, ScreenCapture, SelectionOverlay


@pytest.fixture(scope="module")
def application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        assert isinstance(existing, QApplication)
        return existing
    return QApplication([])


def solid_image(width: int, height: int, color: str) -> QImage:
    image = QImage(width, height, QImage.Format.Format_RGBA8888)
    image.fill(QColor(color))
    return image


def test_native_crop_preserves_physical_pixels():
    screen = ScreenCapture(QRect(0, 0, 100, 50), solid_image(200, 100, "#ff0000"))
    snapshot = DesktopSnapshot(QImage(), QRect(0, 0, 100, 50), (screen,))

    crop = snapshot.crop_native(QRect(10, 5, 20, 10))

    assert (crop.width(), crop.height()) == (40, 20)
    assert crop.pixelColor(20, 10) == QColor("#ff0000")


def test_mixed_dpi_screens_use_highest_capture_scale():
    high_dpi = ScreenCapture(QRect(0, 0, 100, 50), solid_image(200, 100, "#ff0000"))
    standard = ScreenCapture(QRect(100, 0, 100, 50), solid_image(100, 50, "#0000ff"))
    snapshot = DesktopSnapshot(
        QImage(),
        QRect(0, 0, 200, 50),
        (high_dpi, standard),
    )

    crop = snapshot.crop_native(QRect(50, 0, 100, 50))

    assert (crop.width(), crop.height()) == (200, 100)
    assert crop.pixelColor(25, 50) == QColor("#ff0000")
    assert crop.pixelColor(175, 50) == QColor("#0000ff")


def test_crop_outside_snapshot_is_null():
    screen = ScreenCapture(QRect(0, 0, 100, 50), solid_image(100, 50, "#ff0000"))
    snapshot = DesktopSnapshot(QImage(), QRect(0, 0, 100, 50), (screen,))

    assert snapshot.crop_native(QRect(200, 200, 20, 20)).isNull()


def test_closing_selection_overlay_cancels_capture_once(
    application: QApplication,
) -> None:
    image = solid_image(100, 50, "#202020")
    snapshot = DesktopSnapshot(
        image,
        QRect(0, 0, 100, 50),
        (ScreenCapture(QRect(0, 0, 100, 50), image),),
    )
    overlay = SelectionOverlay(snapshot)
    cancellations: list[bool] = []
    overlay.cancelled.connect(lambda: cancellations.append(True))

    overlay.show()
    application.processEvents()
    overlay.close()
    application.processEvents()
    overlay.close()

    assert cancellations == [True]
