"""Application theme styling."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QStyleFactory

from ui.dialog_utils import build_dialog_palette


def apply_app_theme(app: QApplication, mode: str) -> None:
    """Apply the configured light or dark application theme."""
    if "Fusion" in QStyleFactory.keys():
        app.setStyle("Fusion")
    app.setPalette(build_dialog_palette(mode))
    app.setStyleSheet(build_stylesheet(mode))


def build_stylesheet(mode: str) -> str:
    """Return the main application stylesheet for the given mode."""
    dark = mode != "light"
    if dark:
        colors = {
            "window": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(8, 15, 28, 248), stop:0.55 rgba(15, 28, 45, 244), stop:1 rgba(10, 19, 34, 250))",
            "panel": "rgba(18, 30, 48, 0.82)",
            "panel_soft": "rgba(26, 41, 63, 0.62)",
            "surface": "rgba(8, 15, 28, 0.52)",
            "border": "rgba(148, 163, 184, 0.16)",
            "border_soft": "rgba(148, 163, 184, 0.09)",
            "text": "#F8FAFC",
            "muted": "rgba(226, 232, 240, 0.76)",
            "accent": "#5EEAD4",
            "accent_strong": "#22D3EE",
            "accent_soft": "rgba(34, 211, 238, 0.14)",
            "input": "rgba(6, 14, 26, 0.78)",
            "input_hover": "rgba(12, 23, 39, 0.9)",
            "tab": "rgba(15, 26, 43, 0.58)",
            "tab_active": "rgba(20, 34, 54, 0.92)",
            "tab_border": "rgba(94, 234, 212, 0.24)",
            "selection": "rgba(34, 211, 238, 0.18)",
            "scroll": "rgba(148, 163, 184, 0.42)",
        }
    else:
        colors = {
            "window": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(248, 251, 255, 248), stop:0.5 rgba(241, 246, 255, 244), stop:1 rgba(236, 243, 252, 250))",
            "panel": "rgba(255, 255, 255, 0.82)",
            "panel_soft": "rgba(247, 250, 255, 0.86)",
            "surface": "rgba(255, 255, 255, 0.64)",
            "border": "rgba(15, 23, 42, 0.10)",
            "border_soft": "rgba(15, 23, 42, 0.06)",
            "text": "#0F172A",
            "muted": "rgba(51, 65, 85, 0.78)",
            "accent": "#0EA5E9",
            "accent_strong": "#0284C7",
            "accent_soft": "rgba(14, 165, 233, 0.12)",
            "input": "rgba(255, 255, 255, 0.95)",
            "input_hover": "rgba(255, 255, 255, 1)",
            "tab": "rgba(234, 241, 249, 0.92)",
            "tab_active": "rgba(255, 255, 255, 0.98)",
            "tab_border": "rgba(2, 132, 199, 0.42)",
            "selection": "rgba(14, 165, 233, 0.22)",
            "scroll": "rgba(100, 116, 139, 0.30)",
        }

    return f"""
    QWidget {{
        color: {colors['text']};
        font-size: 13px;
        background: transparent;
    }}
    QLabel#heroTitle {{
        color: {colors['text']};
        font-size: 28px;
        font-weight: 700;
    }}
    QLabel#heroSubtitle {{
        color: {colors['muted']};
        font-size: 14px;
    }}
    QMainWindow, QTabWidget::pane, QScrollArea, QScrollArea > QWidget > QWidget {{
        background: {colors['window']};
    }}
    QTabWidget::pane {{
        border: none;
        border-radius: 18px;
        background: {colors['panel']};
        margin-top: 10px;
        padding: 8px 0 0 0;
    }}
    QFrame, QGroupBox {{
        background: {colors['panel']};
        border: 1px solid {colors['border_soft']};
        border-radius: 18px;
    }}
    QGroupBox {{
        margin-top: 18px;
        padding: 18px 18px 16px 18px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 16px;
        top: 1px;
        padding: 3px 10px;
        border-radius: 10px;
        color: {colors['text']};
        background: {colors['surface']};
        border: 1px solid {colors['border']};
    }}
    QPushButton {{
        background: {colors['panel_soft']};
        border: 1px solid {colors['border']};
        border-radius: 12px;
        padding: 8px 16px;
        font-weight: 600;
    }}
    QPushButton[segmented="true"] {{
        min-width: 118px;
        border-radius: 14px;
        padding: 9px 18px;
    }}
    QPushButton[segmented="true"]:checked {{
        background: {colors['accent_soft']};
        border: 1px solid {colors['accent_strong']};
        color: {colors['text']};
    }}
    QPushButton:hover {{
        border-color: {colors['accent_strong']};
        background: {colors['accent_soft']};
    }}
    QPushButton:pressed {{
        background: {colors['selection']};
    }}
    QPushButton:focus {{
        border: 2px solid {colors['accent_strong']};
    }}
    QLabel {{
        background: transparent;
        color: {colors['text']};
    }}
    QTextEdit, QListWidget, QLineEdit, QSpinBox, QComboBox, QKeySequenceEdit {{
        background: {colors['input']};
        border: 1px solid {colors['border']};
        border-radius: 14px;
        padding: 7px 10px;
        selection-background-color: {colors['selection']};
    }}
    QSpinBox {{
        padding-right: 46px;
        min-height: 38px;
    }}
    QSpinBox::up-button, QSpinBox::down-button {{
        width: 22px;
        border: none;
        background: {colors['accent_soft']};
        subcontrol-origin: border;
    }}
    QSpinBox::up-button {{
        subcontrol-position: top right;
        border-top-right-radius: 14px;
        border-left: 1px solid {colors['tab_border']};
        border-bottom: 1px solid {colors['tab_border']};
    }}
    QSpinBox::down-button {{
        subcontrol-position: bottom right;
        border-bottom-right-radius: 14px;
        border-left: 1px solid {colors['tab_border']};
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
        background: {colors['selection']};
    }}
    QSpinBox::up-arrow, QSpinBox::down-arrow {{
        width: 10px;
        height: 10px;
    }}
    QTextEdit:hover, QListWidget:hover, QLineEdit:hover, QSpinBox:hover, QComboBox:hover, QKeySequenceEdit:hover {{
        background: {colors['input_hover']};
        border-color: {colors['tab_border']};
    }}
    QTextEdit:focus, QListWidget:focus, QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QKeySequenceEdit:focus {{
        border: 1px solid {colors['accent_strong']};
    }}
    QMenu, QAbstractItemView {{
        background: {colors['input']};
        color: {colors['text']};
        border: 1px solid {colors['border']};
        border-radius: 14px;
        padding: 6px;
        selection-background-color: {colors['selection']};
        selection-color: {colors['text']};
        outline: none;
    }}
    QMenu::item, QAbstractItemView::item {{
        padding: 8px 14px;
        border-radius: 10px;
        margin: 2px 0;
        color: {colors['text']};
        background: transparent;
    }}
    QMenu::item:selected, QAbstractItemView::item:selected {{
        background: {colors['selection']};
        border: 1px solid {colors['accent_strong']};
        color: {colors['text']};
    }}
    QMenu::separator {{
        height: 1px;
        margin: 6px 8px;
        background: {colors['border_soft']};
    }}
    QComboBox {{
        padding-right: 28px;
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 24px;
        border: none;
        background: transparent;
    }}
    QCheckBox {{
        spacing: 10px;
        font-weight: 600;
    }}
    QCheckBox:focus {{
        color: {colors['accent']};
    }}
    QCheckBox::indicator {{
        width: 34px;
        height: 20px;
        border-radius: 10px;
        border: 1px solid {colors['border']};
        background: {colors['surface']};
    }}
    QCheckBox::indicator:checked {{
        background: {colors['accent']};
        border: 1px solid {colors['accent_strong']};
    }}
    QListWidget {{
        padding: 8px;
        outline: none;
    }}
    QListWidget::item {{
        padding: 11px 12px;
        border-radius: 12px;
        margin: 3px 0;
    }}
    QListWidget::item:hover {{
        background: {colors['accent_soft']};
    }}
    QListWidget::item:selected {{
        background: {colors['selection']};
        border: 1px solid {colors['accent_strong']};
        color: {colors['text']};
        font-weight: 700;
    }}
    QTabBar {{
        background: transparent;
        border: none;
        qproperty-drawBase: 0;
    }}
    QTabWidget::tab-bar {{
        left: 12px;
        top: 4px;
    }}
    QTabBar::tab {{
        background: {colors['tab']};
        border: 1px solid {colors['border']};
        border-bottom: none;
        padding: 11px 20px;
        margin-top: 0;
        margin-right: 8px;
        border-top-left-radius: 16px;
        border-top-right-radius: 16px;
        color: {colors['muted']};
        font-weight: 600;
    }}
    QTabBar::tab:hover {{
        color: {colors['text']};
        border-color: {colors['tab_border']};
    }}
    QTabBar::tab:selected {{
        background: {colors['tab_active']};
        color: {colors['text']};
        border-color: {colors['tab_border']};
        margin-bottom: 0;
    }}
    QTabBar::tab:!selected {{
        margin-top: 4px;
    }}
    QSlider {{
        min-height: 28px;
    }}
    QSlider::groove:horizontal {{
        height: 6px;
        background: {colors['surface']};
        border-radius: 4px;
    }}
    QSlider::sub-page:horizontal {{
        background: {colors['accent_soft']};
        border-radius: 4px;
    }}
    QSlider::handle:horizontal {{
        width: 18px;
        height: 18px;
        margin: -6px 0;
        border-radius: 9px;
        background: {colors['accent']};
        border: 1px solid {colors['tab_border']};
    }}
    QSplitter::handle {{
        background: transparent;
    }}
    QSplitter::handle:horizontal {{
        width: 10px;
        margin: 12px 0;
    }}
    QSplitter::handle:horizontal:hover {{
        background: {colors['accent_soft']};
        border-radius: 5px;
    }}
    QSplitter::handle:vertical {{
        height: 10px;
        margin: 0 12px;
    }}
    QSplitter::handle:vertical:hover {{
        background: {colors['accent_soft']};
        border-radius: 5px;
    }}
    QScrollArea {{
        border: none;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 12px;
        margin: 8px 2px 8px 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {colors['scroll']};
        border-radius: 6px;
        min-height: 30px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
        height: 0;
    }}
    QStatusBar {{
        background: transparent;
        color: {colors['muted']};
    }}
    """
