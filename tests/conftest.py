from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

_application: QApplication | None = None


@pytest.fixture(scope="session", autouse=True)
def qt_application() -> QApplication:
    """Keep one strong application reference throughout the entire test process."""
    global _application
    existing = QApplication.instance()
    _application = existing or QApplication([])
    assert isinstance(_application, QApplication)
    return _application
