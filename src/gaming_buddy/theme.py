STYLESHEET = """
* {
    font-family: "Segoe UI";
    font-size: 13px;
    color: #f4f1ff;
}
QMainWindow, QWidget#panel, QDialog, QWidget#troubleshootingPanel {
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
QFrame#sectionCard {
    background: #171421;
    border: 1px solid #352d47;
    border-radius: 12px;
}
QFrame#undoBar {
    background: #211b34;
    border: 1px solid #594886;
    border-radius: 10px;
}
QFrame#cardPreview {
    background: #191624;
    border: 1px solid #3d3257;
    border-radius: 12px;
}
QDockWidget {
    color: #cdbfff;
    font-weight: 700;
}
QDockWidget::title {
    background: #1b1729;
    border-bottom: 1px solid #3d3257;
    padding: 7px 9px;
    text-align: left;
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
QLabel#previewTitle {
    color: #ffffff;
    font-size: 15px;
    font-weight: 700;
}
QLabel#previewGame {
    color: #d8ccff;
    font-weight: 600;
}
QLabel#previewBadge {
    background: #2b2340;
    border: 1px solid #594886;
    border-radius: 7px;
    color: #cdbfff;
    font-size: 10px;
    font-weight: 700;
    padding: 4px 7px;
}
QLabel#previewImage {
    background: #0a0810;
    border: 1px solid #312941;
    border-radius: 9px;
    color: #817990;
    padding: 4px;
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
QLabel#sectionTitle {
    color: #f7f4ff;
    font-size: 15px;
    font-weight: 700;
}
QLabel#emptyState {
    background: #171421;
    border: 1px dashed #4a3d62;
    border-radius: 10px;
    color: #a9a1bf;
    padding: 16px;
}
QTabWidget#mainTabs::pane, QTabWidget#settingsTabs::pane {
    background: #12101b;
    border: 1px solid #352d47;
    border-radius: 12px;
    top: -1px;
}
QTabWidget#mainTabs QTabBar::tab, QTabWidget#settingsTabs QTabBar::tab {
    background: #191624;
    border: 1px solid #352d47;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    color: #aaa1bd;
    min-width: 50px;
    min-height: 22px;
    padding: 8px 6px;
    margin-right: 2px;
}
QTabWidget#mainTabs QTabBar::tab:hover, QTabWidget#settingsTabs QTabBar::tab:hover {
    background: #252034;
    color: #f4f1ff;
}
QTabWidget#mainTabs QTabBar::tab:selected, QTabWidget#settingsTabs QTabBar::tab:selected {
    background: #2e2645;
    border-color: #7657ff;
    color: #ffffff;
}
QTabWidget#mainTabs QTabBar::tab:focus, QTabWidget#settingsTabs QTabBar::tab:focus {
    border: 2px solid #a893ff;
}
QScrollArea#tabScroll {
    background: #12101b;
    border: none;
}
QScrollArea#tabScroll QWidget#qt_scrollarea_viewport,
QScrollArea#tabScroll QWidget#tabPage {
    background: #12101b;
}
QLineEdit, QTextEdit, QPlainTextEdit, QListWidget, QTableWidget, QComboBox {
    background: #0d0b14;
    border: 1px solid #39304d;
    border-radius: 10px;
    padding: 9px;
    selection-background-color: #7657ff;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QListWidget:focus, QTableWidget:focus, QComboBox:focus {
    border: 1px solid #8a6cff;
}
QTextBrowser#previewText {
    background: #0d0b14;
    border: 1px solid #312941;
    border-radius: 8px;
    color: #e6e0f2;
    padding: 7px;
}
QToolBar#markdownToolbar {
    background: #171321;
    border: 1px solid #39304d;
    border-radius: 8px;
    padding: 3px;
    spacing: 3px;
}
QToolBar#markdownToolbar QToolButton {
    background: #29233a;
    border: 1px solid #44395e;
    border-radius: 6px;
    color: #eee9ff;
    font-weight: 600;
    padding: 5px 8px;
}
QToolBar#markdownToolbar QToolButton:hover {
    background: #3a3052;
    border-color: #7657ff;
}
QToolBar#markdownToolbar QToolButton:pressed { background: #201b2e; }
QPushButton {
    background: #29233a;
    border: 1px solid #44395e;
    border-radius: 9px;
    min-height: 20px;
    padding: 9px 13px;
    font-weight: 600;
}
QPushButton:hover { background: #352d4c; }
QPushButton:pressed { background: #201b2e; }
QPushButton:focus {
    border: 2px solid #a893ff;
    padding: 8px 12px;
}
QPushButton:disabled {
    background: #1b1823;
    border-color: #2d2838;
    color: #716b7d;
}
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
QCheckBox {
    min-height: 28px;
    spacing: 8px;
    color: #c9c1dc;
}
QCheckBox:focus { color: #ffffff; }
QCheckBox:disabled { color: #716b7d; }
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
QSlider:focus::groove:horizontal { background: #594886; }
QScrollBar:vertical {
    background: #12101b;
    border: none;
    width: 12px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #514268;
    border-radius: 6px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover { background: #7657ff; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QListWidget::item {
    padding: 9px;
    border-bottom: 1px solid #282235;
}
QListWidget::item:selected { background: #30264c; }
QListWidget#cardLibrary { alternate-background-color: #14111d; }
QListWidget#cardLibrary::item:hover { background: #241e32; }
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
