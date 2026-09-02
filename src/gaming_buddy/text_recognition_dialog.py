from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gaming_buddy.text_recognition import (
    RecognitionLanguage,
    RecognitionResult,
    recognize_text,
)


class _RecognitionWorker(QObject):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        image_path: Path,
        language: str,
        recognizer: Callable[[Path, str], RecognitionResult],
    ) -> None:
        super().__init__()
        self._image_path = image_path
        self._language = language
        self._recognizer = recognizer

    @Slot()
    def run(self) -> None:
        try:
            result = self._recognizer(self._image_path, self._language)
        except Exception as exc:  # noqa: BLE001 - worker must always report and stop cleanly
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(result)


class TextRecognitionDialog(QDialog):
    def __init__(
        self,
        image_path: Path,
        existing_text: str,
        languages: Sequence[RecognitionLanguage],
        preferred_language: str = "",
        parent: QWidget | None = None,
        *,
        recognizer: Callable[[Path, str], RecognitionResult] = recognize_text,
        auto_start: bool = True,
    ) -> None:
        super().__init__(parent)
        self._image_path = image_path
        self._recognizer = recognizer
        self._thread: QThread | None = None
        self._worker: _RecognitionWorker | None = None

        self.setWindowTitle("Extract screenshot text")
        self.setMinimumSize(560, 480)
        self.resize(680, 580)
        self.setModal(False)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        title = QLabel("Extract text from screenshot")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        description = QLabel(
            "Recognition runs locally with Windows language packs. Review and correct "
            "the result before saving it to the card."
        )
        description.setObjectName("muted")
        description.setWordWrap(True)
        layout.addWidget(description)

        controls = QHBoxLayout()
        language_label = QLabel("Language")
        language_label.setObjectName("muted")
        self.language = QComboBox()
        self.language.addItem("Automatic (Windows profile)", "")
        selected_index = 0
        for item in languages:
            self.language.addItem(f"{item.display_name} ({item.tag})", item.tag)
            if item.tag.casefold() == preferred_language.casefold():
                selected_index = self.language.count() - 1
        self.language.setCurrentIndex(selected_index)
        self.recognize_button = QPushButton("Recognize text")
        self.recognize_button.setObjectName("primary")
        self.recognize_button.clicked.connect(self.start_recognition)
        controls.addWidget(language_label)
        controls.addWidget(self.language, 1)
        controls.addWidget(self.recognize_button)
        layout.addLayout(controls)

        self.status = QLabel("Ready")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.text = QTextEdit(existing_text)
        self.text.setPlaceholderText("Recognized text will appear here…")
        layout.addWidget(self.text, 1)

        footer = QHBoxLayout()
        copy_button = QPushButton("Copy text")
        copy_button.clicked.connect(self.copy_text)
        footer.addWidget(copy_button)
        footer.addStretch(1)
        self.dialog_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.dialog_buttons.accepted.connect(self.accept)
        self.dialog_buttons.rejected.connect(self.reject)
        footer.addWidget(self.dialog_buttons)
        layout.addLayout(footer)

        if auto_start:
            QTimer.singleShot(0, self.start_recognition)

    @property
    def selected_language(self) -> str:
        return str(self.language.currentData() or "")

    @property
    def recognized_text(self) -> str:
        return self.text.toPlainText().strip()

    def start_recognition(self) -> None:
        if self._thread is not None:
            return
        self.recognize_button.setEnabled(False)
        self.language.setEnabled(False)
        self.dialog_buttons.setEnabled(False)
        self.status.setText("Reading the screenshot…")

        thread = QThread(self)
        worker = _RecognitionWorker(
            self._image_path,
            self.selected_language,
            self._recognizer,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self._recognition_succeeded)
        worker.failed.connect(self._recognition_failed)
        worker.succeeded.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._recognition_finished)
        self._thread = thread
        self._worker = worker
        thread.start()

    @Slot(object)
    def _recognition_succeeded(self, result: object) -> None:
        if not isinstance(result, RecognitionResult):
            self._recognition_failed("Windows returned an invalid recognition result.")
            return
        self.text.setPlainText(result.text)
        if result.text:
            self.status.setText(f"Text recognized using {result.language}.")
        else:
            self.status.setText(
                "No readable text was found. Try a tighter crop or another language."
            )

    @Slot(str)
    def _recognition_failed(self, message: str) -> None:
        self.status.setText(f"Could not recognize text: {message}")

    @Slot()
    def _recognition_finished(self) -> None:
        thread = self._thread
        self._thread = None
        self._worker = None
        self.recognize_button.setEnabled(True)
        self.language.setEnabled(True)
        self.dialog_buttons.setEnabled(True)
        if thread is not None:
            thread.deleteLater()

    def copy_text(self) -> None:
        text = self.recognized_text
        if not text:
            self.status.setText("There is no text to copy yet.")
            return
        QApplication.clipboard().setText(text)
        self.status.setText("Text copied to the clipboard.")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._thread is not None and self._thread.isRunning():
            self.status.setText("Wait for recognition to finish before closing this window.")
            event.ignore()
            return
        super().closeEvent(event)

    def accept(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            self.status.setText("Wait for recognition to finish before saving.")
            return
        super().accept()

    def reject(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            self.status.setText("Wait for recognition to finish before closing this window.")
            return
        super().reject()
