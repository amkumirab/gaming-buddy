from __future__ import annotations

from enum import StrEnum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gaming_buddy.updates import ReleaseInfo


class UpdateAction(StrEnum):
    DOWNLOAD = "download"
    VIEW_RELEASE = "view_release"


class UpdateDialog(QDialog):
    def __init__(
        self,
        current_version: str,
        release: ReleaseInfo,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.action: UpdateAction | None = None
        self.setWindowTitle("Gaming Buddy update")
        self.setModal(True)
        self.resize(560, 430)

        layout = QVBoxLayout(self)
        title = QLabel("A new version is ready")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        versions = QLabel(f"Installed: {current_version}    Available: {release.version}")
        versions.setObjectName("muted")
        layout.addWidget(versions)

        release_title = QLabel(release.title)
        release_title.setWordWrap(True)
        layout.addWidget(release_title)

        notes = QPlainTextEdit()
        notes.setReadOnly(True)
        notes.setPlainText(release.notes or "No release notes were provided.")
        notes.setAccessibleName("Release notes")
        layout.addWidget(notes, 1)

        safety = QLabel(
            "The installer will be verified before it runs. Installation starts only after "
            "your confirmation."
        )
        safety.setObjectName("muted")
        safety.setWordWrap(True)
        layout.addWidget(safety)

        buttons = QHBoxLayout()
        later = QPushButton("Later")
        later.clicked.connect(self.reject)
        view = QPushButton("View release page")
        view.clicked.connect(lambda: self._choose(UpdateAction.VIEW_RELEASE))
        download = QPushButton("Download and install")
        download.setObjectName("primary")
        download.setDefault(True)
        download.clicked.connect(lambda: self._choose(UpdateAction.DOWNLOAD))
        buttons.addStretch(1)
        buttons.addWidget(later)
        buttons.addWidget(view)
        buttons.addWidget(download)
        layout.addLayout(buttons)

        self.setWindowModality(Qt.WindowModality.ApplicationModal)

    def _choose(self, action: UpdateAction) -> None:
        self.action = action
        self.accept()
