"""Design system for the GP Fleet Console.

One palette, one QSS sheet, one card component — every widget pulls from
here so the whole app stays visually coherent. Applied once in main.py
(Fusion base style + this stylesheet).
"""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

# ── Palette ───────────────────────────────────────────────────────────────
BG        = '#0a0e16'   # app background
SURFACE   = '#111827'   # cards
SURFACE_2 = '#1a2333'   # raised / hover
BORDER    = '#243047'
ACCENT    = '#38bdf8'   # primary cyan-blue
ACCENT_D  = '#0284c7'
TEXT      = '#e5eaf2'
MUTED     = '#8b96ab'
GOOD      = '#34d399'
WARN      = '#fbbf24'
BAD       = '#f87171'
DANGER    = '#dc2626'
DANGER_D  = '#991b1b'
MONO      = 'Consolas, "Cascadia Mono", monospace'

# Map rendering colors (BGR-free, used as RGB tuples in map_view)
MAP_UNKNOWN = (34, 40, 54)
MAP_FREE    = (226, 231, 238)
MAP_OCCUPIED = (8, 10, 15)

# ── Application stylesheet ────────────────────────────────────────────────
QSS = f"""
QMainWindow, QDialog {{ background: {BG}; }}
QWidget {{ color: {TEXT}; font-family: 'Segoe UI'; font-size: 13px; }}
QLabel {{ background: transparent; }}

/* ── Cards & section titles ───────────────────────────────────────── */
QFrame#card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QLabel#sectionTitle {{
    color: {MUTED};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
}}
QLabel#chip {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 3px 10px;
    color: {MUTED};
    font-family: {MONO};
    font-size: 11px;
}}

/* ── Alert banner ─────────────────────────────────────────────────── */
QFrame#alertBanner {{
    border-radius: 10px;
    border: 1px solid #7f1d1d;
}}
QLabel#alertText {{
    color: white;
    font-size: 14px;
    font-weight: 800;
    letter-spacing: 1px;
    background: transparent;
}}
QPushButton#ackBtn {{
    background: rgba(255, 255, 255, 0.14);
    border: 1px solid rgba(255, 255, 255, 0.45);
    border-radius: 7px;
    color: white;
    font-weight: 800;
    padding: 5px 16px;
}}
QPushButton#ackBtn:hover {{ background: rgba(255, 255, 255, 0.28); }}

/* ── Exit button (toolbar) ────────────────────────────────────────── */
QPushButton#exitBtn {{
    background: transparent;
    border: 1px solid #7f1d1d;
    border-radius: 7px;
    color: {BAD};
    font-weight: 700;
    padding: 5px 14px;
}}
QPushButton#exitBtn:hover {{ background: #7f1d1d; color: white; }}
QPushButton#exitBtn:pressed {{ background: {DANGER}; color: white; }}

/* ── Toolbar ──────────────────────────────────────────────────────── */
QToolBar {{
    background: {SURFACE};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 7px 12px;
    spacing: 10px;
}}
QLabel#appTitle {{
    color: {TEXT};
    font-size: 15px;
    font-weight: 800;
    letter-spacing: 3px;
    padding-right: 14px;
}}
QLabel#appTitle b {{ color: {ACCENT}; }}

/* ── Buttons ──────────────────────────────────────────────────────── */
QPushButton {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 14px;
    color: {TEXT};
    font-weight: 600;
}}
QPushButton:hover {{ background: #223049; border-color: {ACCENT_D}; }}
QPushButton:pressed {{ background: {ACCENT_D}; color: white; }}
QPushButton:disabled {{ color: #525d70; background: {SURFACE}; }}

QPushButton#dpadBtn {{
    background: #1c2a44;
    border: 1px solid #2c3e63;
    font-size: 17px;
    color: {ACCENT};
}}
QPushButton#dpadBtn:hover {{ background: #24375c; }}
QPushButton#dpadBtn:pressed {{ background: {ACCENT_D}; color: white; }}

QPushButton#stopBtn {{
    background: {SURFACE_2};
    font-size: 15px;
    color: {MUTED};
}}
QPushButton#stopBtn:pressed {{ background: #475569; color: white; }}

QPushButton#pumpBtn {{
    background: #0c3349;
    border: 1px solid #155e85;
    color: #7dd3fc;
    font-weight: 700;
}}
QPushButton#pumpBtn:hover {{ background: #11405c; }}
QPushButton#pumpBtn:pressed {{ background: #0369a1; color: white; }}

QPushButton#exploreBtn {{
    color: {MUTED};
    font-weight: 700;
    letter-spacing: 1px;
}}
QPushButton#exploreBtn:checked {{
    background: #14323d;
    border-color: {ACCENT};
    color: {ACCENT};
}}
QPushButton#fitBtn {{
    padding: 2px 10px;
    font-size: 11px;
    color: {MUTED};
    border-radius: 6px;
}}

/* ── Group boxes (control panel sections) ─────────────────────────── */
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 10px;
    margin-top: 11px;
    padding: 10px 8px 8px 8px;
    font-size: 11px;
    font-weight: 700;
    color: {MUTED};
    letter-spacing: 1px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    background: {SURFACE};
}}

/* ── Sliders ──────────────────────────────────────────────────────── */
QSlider::groove:horizontal {{
    height: 5px;
    background: {SURFACE_2};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{ background: {ACCENT_D}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    width: 16px; height: 16px;
    margin: -6px 0;
    border-radius: 8px;
    background: {ACCENT};
    border: 2px solid {BG};
}}
QSlider::handle:horizontal:hover {{ background: #7dd3fc; }}

/* ── Combo boxes ──────────────────────────────────────────────────── */
QComboBox {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 5px 28px 5px 10px;
    min-width: 130px;
    font-weight: 600;
}}
QComboBox:hover {{ border-color: {ACCENT_D}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {MUTED};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 7px;
    selection-background-color: {ACCENT_D};
    selection-color: white;
    outline: none;
    padding: 4px;
}}

/* ── Tabs ─────────────────────────────────────────────────────────── */
QTabWidget::pane {{ border: none; top: 6px; }}
QTabBar::tab {{
    background: transparent;
    color: {MUTED};
    padding: 7px 18px;
    margin-right: 4px;
    border-radius: 7px;
    font-weight: 700;
    letter-spacing: 1px;
    font-size: 12px;
}}
QTabBar::tab:hover {{ background: {SURFACE_2}; }}
QTabBar::tab:selected {{ background: {SURFACE_2}; color: {ACCENT}; }}

/* ── Splitters / scrollbars / status bar ──────────────────────────── */
QSplitter::handle {{ background: {BG}; }}
QSplitter::handle:horizontal {{ width: 7px; }}
QSplitter::handle:vertical {{ height: 7px; }}

QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: {SURFACE_2}; border-radius: 4px; min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: #2d3b57; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: {SURFACE_2}; border-radius: 4px; min-width: 28px;
}}

QStatusBar {{
    background: {SURFACE};
    border-top: 1px solid {BORDER};
    color: {MUTED};
    font-family: {MONO};
    font-size: 11px;
}}
QStatusBar QLabel {{ padding: 0 10px; font-family: {MONO}; font-size: 11px; }}

QPlainTextEdit {{
    background: #0d1422;
    border: none;
    border-radius: 8px;
}}
"""

# Inline state styles (swapped at runtime — avoids QSS repolish dances)
ESTOP_IDLE = (f'background:{DANGER}; color:white; font-weight:800; '
              f'font-size:14px; letter-spacing:2px; border:1px solid {DANGER_D}; '
              'border-radius:10px;')
ESTOP_ENGAGED = ('background:#b45309; color:white; font-weight:800; '
                 'font-size:14px; letter-spacing:2px; border:1px solid #92400e; '
                 'border-radius:10px;')

# Alert banner backgrounds (pulse alternates A/B while unacknowledged)
BANNER_FIRE_A = 'background:#b91c1c;'
BANNER_FIRE_B = 'background:#7f1d1d;'
BANNER_GAS_A  = 'background:#b45309;'
BANNER_GAS_B  = 'background:#78350f;'
BANNER_ACKED  = 'background:#52525b;'


class Card(QFrame):
    """Rounded surface with an optional uppercase section title row.

    card = Card('LIVE FEED');  card.body.addWidget(video)
    Extra header widgets (e.g. a Fit button) go via card.header.addWidget().
    """

    def __init__(self, title: str | None = None, parent: QWidget | None = None,
                 padding: int = 10):
        super().__init__(parent)
        self.setObjectName('card')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(padding, padding, padding, padding)
        outer.setSpacing(6)

        self.header = QHBoxLayout()
        self.header.setContentsMargins(2, 0, 2, 0)
        if title:
            lbl = QLabel(title)
            lbl.setObjectName('sectionTitle')
            self.header.addWidget(lbl)
        self.header.addStretch(1)
        outer.addLayout(self.header)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(6)
        outer.addLayout(self.body, 1)


def chip(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName('chip')
    return lbl


def enable_dark_titlebar(widget) -> None:
    """Windows: ask DWM for a dark title bar so the frame matches the app."""
    try:
        import ctypes
        hwnd = int(widget.winId())
        value = ctypes.c_int(1)
        for attr in (20, 19):     # DWMWA_USE_IMMERSIVE_DARK_MODE (19 pre-20H1)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
    except Exception:
        pass                      # non-Windows or old build — cosmetic only
