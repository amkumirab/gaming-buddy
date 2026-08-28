STYLESHEET = """
* {
    font-family: "Segoe UI";
    font-size: 13px;
    color: #f4f1ff;
}
QMainWindow, QWidget#panel, QDialog {
    background: #12101b;
}
QFrame#hero {
    background: #1b1729;
    border: 1px solid #352b52;
    border-radius: 16px;
}
QFrame#setupCard {
    background: #191624;
    border: 1px solid #352b52;
    border-radius: 12px;
}
QFrame#undoBar {
    background: #211b34;
    border: 1px solid #594886;
    border-radius: 10px;
}
QLabel#brand {
    font-size: 22px;
    font-weight: 700;
    color: #ffffff;
}
QLabel#setupTitle {
    color: #ffffff;
    font-size: 21px;
    font-weight: 700;
}
QLabel#dialogTitle {
    color: #ffffff;
    font-size: 20px;
    font-weight: 700;
}
QLabel#setupHeading {
    color: #ffffff;
    font-size: 14px;
    font-weight: 700;
}
QLabel#setupStep {
    background: #7657ff;
    border: 1px solid #947fff;
    border-radius: 16px;
    color: #ffffff;
    font-weight: 700;
}
QLabel#setupNotice {
    background: #211b34;
    border: 1px solid #594886;
    border-radius: 10px;
    color: #d8ccff;
    padding: 10px;
}
QLabel#subtitle, QLabel#muted {
    color: #a9a1bf;
}
QLabel#section {
    color: #bca8ff;
    font-size: 12px;
    font-weight: 700;
}
QLineEdit, QTextEdit, QListWidget, QTableWidget, QComboBox {
    background: #0d0b14;
    border: 1px solid #39304d;
    border-radius: 10px;
    padding: 9px;
    selection-background-color: #7657ff;
}
QLineEdit:focus, QTextEdit:focus, QListWidget:focus, QTableWidget:focus, QComboBox:focus {
    border: 1px solid #8a6cff;
}
QPushButton {
    background: #29233a;
    border: 1px solid #44395e;
    border-radius: 9px;
    padding: 9px 13px;
    font-weight: 600;
}
QPushButton:hover { background: #352d4c; }
QPushButton:pressed { background: #201b2e; }
QPushButton:checked {
    background: #7657ff;
    border-color: #947fff;
}
QPushButton#primary {
    background: #7657ff;
    border-color: #947fff;
}
QPushButton#primary:hover { background: #866cff; }
QPushButton#danger { color: #ff9da8; }
QPushButton#compact { padding: 5px 9px; }
QCheckBox { spacing: 8px; color: #c9c1dc; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: #191522;
    border: 1px solid #403653;
    selection-background-color: #7657ff;
}
QSlider::groove:horizontal {
    height: 5px;
    background: #39304d;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 16px;
    margin: -6px 0;
    background: #8a6cff;
    border-radius: 8px;
}
QListWidget::item {
    padding: 9px;
    border-bottom: 1px solid #282235;
}
QListWidget::item:selected { background: #30264c; }
QTableWidget::item { padding: 7px; }
QTableWidget::item:selected { background: #30264c; }
QHeaderView::section {
    background: #1b1729;
    color: #bca8ff;
    border: none;
    border-bottom: 1px solid #39304d;
    padding: 8px;
    font-weight: 700;
}
QMenu {
    background: #191522;
    border: 1px solid #403653;
    padding: 5px;
}
QMenu::item { padding: 7px 24px; border-radius: 5px; }
QMenu::item:selected { background: #7657ff; }
"""
