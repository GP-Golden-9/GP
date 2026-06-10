"""Design system for the GP Operations Center.

One palette, one stylesheet, shared micro-components. Every UI module pulls
from here — nothing styles itself ad hoc.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

# ── Palette ───────────────────────────────────────────────────────────────
BG        = '#0a0d14'
SURFACE   = '#10141d'
SURFACE_2 = '#171d2a'
SURFACE_3 = '#1f2737'
BORDER    = '#222b3d'
ACCENT    = '#3da9fc'
ACCENT_D  = '#1572b8'
TEXT      = '#e6eaf2'
MUTED     = '#79849a'
GOOD      = '#2dd4a7'
WARN      = '#f5b941'
BAD       = '#f4647c'
DANGER    = '#d92638'
DANGER_D  = '#8f1622'
MONO      = 'Consolas, "Cascadia Mono", monospace'

# Map colors
MAP_BG       = '#0b0f17'
MAP_UNKNOWN  = (21, 26, 38)
MAP_FREE     = (216, 222, 233)
MAP_OCCUPIED = (3, 5, 9)
MAP_GRIDLINE = (122, 148, 188, 26)
ROBOT_ACTIVE = '#2dd4a7'
ROBOT_OTHER  = '#5b6b8c'
SCAN_COLOR   = '#f4647c'
TRAIL_ACTIVE = (45, 212, 167, 90)
TRAIL_OTHER  = (91, 107, 140, 70)
GOAL_COLOR   = '#f4647c'
GOAL_LINE    = '#f5b941'
MARKER_FIRE  = '#ff6b35'
MARKER_GAS   = '#f5b941'
MARKER_PIN   = '#3da9fc'

QSS = f"""
QMainWindow, QDialog {{ background: {BG}; }}
QWidget {{ color: {TEXT}; font-family: 'Segoe UI'; font-size: 13px; }}
QLabel {{ background: transparent; }}
QToolTip {{ background: {SURFACE_3}; color: {TEXT}; border: 1px solid {BORDER}; }}

/* ── Docks ────────────────────────────────────────────────────────── */
QDockWidget {{
    color: {MUTED};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}}
QDockWidget::title {{
    background: {SURFACE};
    border-bottom: 1px solid {BORDER};
    padding: 6px 10px;
    text-align: left;
}}
QDockWidget > QWidget {{ background: {SURFACE}; }}
QMainWindow::separator {{ background: {BG}; width: 5px; height: 5px; }}
QMainWindow::separator:hover {{ background: {ACCENT_D}; }}

/* ── Menus ────────────────────────────────────────────────────────── */
QMenuBar {{ background: {SURFACE}; border-bottom: 1px solid {BORDER}; padding: 2px 6px; }}
QMenuBar::item {{ padding: 5px 10px; border-radius: 6px; color: {MUTED}; }}
QMenuBar::item:selected {{ background: {SURFACE_2}; color: {TEXT}; }}
QMenu {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 8px; padding: 5px; }}
QMenu::item {{ padding: 6px 22px 6px 14px; border-radius: 5px; }}
QMenu::item:selected {{ background: {ACCENT_D}; color: white; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 5px 8px; }}
QMenu::indicator:checked {{ background: {ACCENT}; border-radius: 3px; width: 8px; height: 8px; margin-left: 4px; }}

/* ── Command bar ──────────────────────────────────────────────────── */
QToolBar {{
    background: {SURFACE};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 6px 10px;
    spacing: 8px;
}}
QLabel#appTitle {{
    color: {TEXT}; font-size: 14px; font-weight: 800; letter-spacing: 3px;
    padding-right: 10px;
}}
QLabel#appTitle b {{ color: {ACCENT}; }}
QLabel#chip {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 9px;
    padding: 3px 10px; color: {MUTED}; font-family: {MONO}; font-size: 11px;
}}
QPushButton#robotPill {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 15px;
    padding: 5px 14px; font-weight: 700; color: {MUTED}; font-size: 12px;
}}
QPushButton#robotPill:hover {{ border-color: {ACCENT_D}; color: {TEXT}; }}
QPushButton#robotPill:checked {{
    background: #12314d; border-color: {ACCENT}; color: {ACCENT};
}}
QPushButton#allStopBtn {{
    background: {DANGER}; border: 1px solid {DANGER_D}; border-radius: 8px;
    color: white; font-weight: 800; letter-spacing: 1px; padding: 6px 16px;
}}
QPushButton#allStopBtn:hover {{ background: #ef3347; }}
QPushButton#exitBtn {{
    background: transparent; border: 1px solid {DANGER_D}; border-radius: 7px;
    color: {BAD}; font-weight: 700; padding: 5px 14px;
}}
QPushButton#exitBtn:hover {{ background: {DANGER_D}; color: white; }}

/* ── Generic controls ─────────────────────────────────────────────── */
QPushButton {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 7px;
    padding: 6px 12px; color: {TEXT}; font-weight: 600;
}}
QPushButton:hover {{ background: {SURFACE_3}; border-color: {ACCENT_D}; }}
QPushButton:pressed {{ background: {ACCENT_D}; color: white; }}
QPushButton:disabled {{ color: #4b5568; background: {SURFACE}; }}
QPushButton:checked {{ background: #12314d; border-color: {ACCENT}; color: {ACCENT}; }}

QToolButton {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 6px;
    padding: 4px 8px; color: {MUTED}; font-weight: 700; font-size: 11px;
}}
QToolButton:hover {{ border-color: {ACCENT_D}; color: {TEXT}; }}
QToolButton:checked {{ background: #12314d; border-color: {ACCENT}; color: {ACCENT}; }}
QToolButton::menu-indicator {{ image: none; }}

QComboBox {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 7px;
    padding: 5px 26px 5px 10px; min-width: 110px; font-weight: 600;
}}
QComboBox:hover {{ border-color: {ACCENT_D}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{
    image: none; border-left: 4px solid transparent;
    border-right: 4px solid transparent; border-top: 5px solid {MUTED};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 7px;
    selection-background-color: {ACCENT_D}; selection-color: white;
    outline: none; padding: 4px;
}}

QSlider::groove:horizontal {{ height: 5px; background: {SURFACE_3}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT_D}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    width: 15px; height: 15px; margin: -5px 0; border-radius: 7px;
    background: {ACCENT}; border: 2px solid {BG};
}}
QSlider::handle:horizontal:hover {{ background: #74c4ff; }}

QTabWidget::pane {{ border: none; top: 4px; }}
QTabBar::tab {{
    background: transparent; color: {MUTED}; padding: 6px 16px; margin-right: 3px;
    border-radius: 6px; font-weight: 700; letter-spacing: 1px; font-size: 11px;
}}
QTabBar::tab:hover {{ background: {SURFACE_2}; }}
QTabBar::tab:selected {{ background: {SURFACE_2}; color: {ACCENT}; }}

QTableWidget {{
    background: {SURFACE}; border: none; gridline-color: {BORDER};
    font-family: {MONO}; font-size: 11px;
    selection-background-color: {ACCENT_D}; selection-color: white;
}}
QHeaderView::section {{
    background: {SURFACE_2}; color: {MUTED}; border: none;
    border-bottom: 1px solid {BORDER}; padding: 5px 8px;
    font-weight: 700; font-size: 10px; letter-spacing: 1px;
}}

QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {SURFACE_3}; border-radius: 4px; min-height: 26px; }}
QScrollBar::handle:vertical:hover {{ background: #2c3850; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {SURFACE_3}; border-radius: 4px; min-width: 26px; }}

QStatusBar {{
    background: {SURFACE}; border-top: 1px solid {BORDER}; color: {MUTED};
    font-family: {MONO}; font-size: 11px;
}}
QStatusBar QLabel {{ padding: 0 10px; font-family: {MONO}; font-size: 11px; }}

QPlainTextEdit {{ background: #0c1019; border: none; border-radius: 8px; }}
QGroupBox {{
    border: 1px solid {BORDER}; border-radius: 9px; margin-top: 10px;
    padding: 9px 8px 8px 8px; font-size: 10px; font-weight: 700;
    color: {MUTED}; letter-spacing: 1px;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px;
                    background: {SURFACE}; }}
QFrame#alertBanner {{ border-radius: 0; border: none; }}
QLabel#alertText {{
    color: white; font-size: 13px; font-weight: 800; letter-spacing: 1px;
    background: transparent;
}}
QPushButton#ackBtn {{
    background: rgba(255,255,255,0.14); border: 1px solid rgba(255,255,255,0.45);
    border-radius: 7px; color: white; font-weight: 800; padding: 4px 14px;
}}
QPushButton#ackBtn:hover {{ background: rgba(255,255,255,0.28); }}

/* Map overlay chips (children of the canvas) */
QFrame#mapToolbar {{
    background: rgba(13, 17, 26, 0.88); border: 1px solid {BORDER};
    border-radius: 9px;
}}
QLabel#mapChip {{
    background: rgba(13, 17, 26, 0.85); border: 1px solid {BORDER};
    border-radius: 8px; padding: 3px 10px; color: {MUTED};
    font-family: {MONO}; font-size: 11px;
}}
"""

# Runtime-swapped inline styles
ESTOP_IDLE = (f'background:{DANGER}; color:white; font-weight:800; font-size:13px;'
              f'letter-spacing:2px; border:1px solid {DANGER_D}; border-radius:9px;')
ESTOP_ENGAGED = ('background:#b45309; color:white; font-weight:800; font-size:13px;'
                 'letter-spacing:2px; border:1px solid #92400e; border-radius:9px;')
BANNER_FIRE_A = 'background:#c01425;'
BANNER_FIRE_B = 'background:#7c0d1a;'
BANNER_GAS_A = 'background:#b45309;'
BANNER_GAS_B = 'background:#78350f;'
BANNER_ACKED = 'background:#4b5563;'

LED_STYLE = f'font-family:{MONO}; font-size:11px;'


def section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f'color:{MUTED}; font-size:10px; font-weight:700; '
                      'letter-spacing:2px;')
    return lbl


def chip(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName('chip')
    return lbl


def enable_dark_titlebar(widget) -> None:
    """Windows: dark DWM title bar so the frame matches the app."""
    try:
        import ctypes
        hwnd = int(widget.winId())
        value = ctypes.c_int(1)
        for attr in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
    except Exception:
        pass
