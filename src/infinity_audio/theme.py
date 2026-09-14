DARK={"bg":"#10141d","panel":"#181e29","raised":"#222b3a","line":"#2c3749","text":"#e8edf7","muted":"#99a8c0","accent":"#aa96ff","button":"#8270eb"}
LIGHT={"bg":"#f3f5fb","panel":"#ffffff","raised":"#e9edf6","line":"#d5dced","text":"#232d43","muted":"#5e6c85","accent":"#6350cb","button":"#7460df"}


def stylesheet(light=False):
    c=LIGHT if light else DARK
    return f'''
    QWidget {{ font-family: "Segoe UI", "DejaVu Sans"; font-size: 12px; color:{c["text"]}; }}
    QMainWindow, QDialog {{ background:{c["bg"]}; }}
    QWidget#Mixer {{ background:{c["bg"]}; }}
    QFrame#Panel, QWidget#Panel {{ background:{c["panel"]}; border:1px solid {c["line"]}; border-radius:10px; }}
    QLabel#Muted {{ color:{c["muted"]}; font-size:11px; }}
    QLabel#Eyebrow {{ color:{c["muted"]}; font-size:10px; font-weight:600; letter-spacing:1px; }}
    QLabel#Brand {{ font-size:23px; font-weight:700; }}
    QLabel#Infinity {{ color:{c["accent"]}; font-size:38px; font-weight:600; }}
    QLabel#Title {{ font-size:18px; font-weight:600; }}
    QLabel#Pill {{ background:{c["raised"]}; color:{c["accent"]}; border-radius:9px; padding:5px 10px; }}
    QPushButton {{ background:{c["raised"]}; border:1px solid {c["line"]}; border-radius:6px; padding:7px 10px; min-height:18px; }}
    QPushButton:hover {{ border-color:{c["accent"]}; }}
    QPushButton:pressed,QPushButton:checked {{ background:{c["button"]}; color:white; }}
    QPushButton:disabled {{ color:{c["muted"]}; background:{c["panel"]}; }}
    QPushButton#Primary {{ background:{c["button"]}; color:white; font-weight:600; border-color:{c["button"]}; }}
    QPushButton#Play {{ background:{c["button"]}; color:white; font-size:17px; min-width:35px; }}
    QComboBox,QSpinBox,QDoubleSpinBox,QLineEdit,QPlainTextEdit {{ background:{c["bg"]}; border:1px solid {c["line"]}; border-radius:5px; padding:5px; min-height:19px; selection-background-color:{c["button"]}; }}
    QComboBox::drop-down {{ border:0px; width:18px; }}
    QComboBox QAbstractItemView {{ background:{c["panel"]}; selection-background-color:{c["button"]}; }}
    QListWidget,QTableWidget,QScrollArea {{ background:{c["bg"]}; border:1px solid {c["line"]}; border-radius:6px; }}
    QListWidget::item {{ padding:8px 6px; border-bottom:1px solid {c["line"]}; }}
    QListWidget::item:selected {{ background:{c["raised"]}; color:{c["accent"]}; }}
    QHeaderView::section {{ background:{c["raised"]}; border:0; padding:6px; }}
    QTabWidget::pane {{ border:0; }}
    QTabBar::tab {{ color:{c["muted"]}; padding:9px 11px; border-bottom:2px solid transparent; }}
    QTabBar::tab:selected {{ color:{c["accent"]}; border-bottom:2px solid {c["accent"]}; }}
    QSlider::groove:horizontal {{ height:4px; background:{c["line"]}; border-radius:2px; }}
    QSlider::sub-page:horizontal {{ background:{c["button"]}; border-radius:2px; }}
    QSlider::handle:horizontal {{ width:12px; margin:-4px 0; background:{c["accent"]}; border-radius:6px; }}
    QProgressBar {{ border:0; background:{c["raised"]}; border-radius:4px; height:7px; text-align:center; }}
    QProgressBar::chunk {{ background:{c["button"]}; border-radius:4px; }}
    QMenuBar,QMenu,QStatusBar {{ background:{c["panel"]}; }}
    QMenu::item {{ padding:6px 25px; }} QMenu::item:selected {{ background:{c["raised"]}; }}
    QToolTip {{ background:{c["raised"]}; color:{c["text"]}; border:1px solid {c["line"]}; padding:6px; }}
    QScrollBar:vertical {{ background:{c["bg"]}; width:10px; }}
    QScrollBar:horizontal {{ background:{c["bg"]}; height:10px; }}
    QScrollBar::handle {{ background:{c["line"]}; border-radius:4px; min-height:25px; min-width:25px; }}
    QScrollBar::add-line,QScrollBar::sub-line {{ width:0; height:0; }}
    QSplitter::handle {{ background:transparent; width:8px; height:8px; }}
    '''
