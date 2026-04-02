from PyQt6.QtCore import Qt, QPropertyAnimation, QRect, QTimer
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QPushButton, QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QBrush, QFont


class BackspaceButton(QPushButton):
    def __init__(self, text="×", parent=None):
        super().__init__(text, parent)
        self._bg = QColor("#2c2c2e")
        self._fg = QColor("#ffffff")
        self.setFixedSize(36, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_colors(self, bg: QColor, fg: QColor):
        self._bg = bg
        self._fg = fg
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        h = self.height()
        notch = 12
        radius = 8

        path = QPainterPath()
        path.moveTo(notch, 0)
        path.lineTo(w - radius, 0)
        path.quadTo(w, 0, w, radius)
        path.lineTo(w, h - radius)
        path.quadTo(w, h, w - radius, h)
        path.lineTo(notch, h)
        path.lineTo(0, h / 2)
        path.closeSubpath()

        painter.setPen(QPen(self._bg))
        painter.setBrush(QBrush(self._bg))
        painter.drawPath(path)

        painter.setPen(QPen(self._fg))
        font = QFont(self.font())
        font.setPointSize(20)
        font.setBold(True)
        painter.setFont(font)
        text_rect = self.rect()
        text_rect.setLeft(notch)
        text_rect.adjust(0, -1, 0, -1)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self.text())


def build_dialer_page(on_digit, on_call, on_backspace, on_clear, on_settings=None):
    dialer_page = QWidget()
    layout = QVBoxLayout(dialer_page)
    layout.setSpacing(12)
    layout.setContentsMargins(16, 16, 16, 16)

    # ---------- STYLE ----------
    LIGHT_STYLE = """
    QWidget { background-color: #ffffff; color: #000000; }
    QLabel#dialDisplay { font-size: 34px; font-weight: 600; letter-spacing: 3px; }
    QLabel#status { color: #8e8e93; font-size: 13px; }

    QPushButton#dialBtn {
        background-color: #ffffff;
        border: 1px solid #d1d1d6;
        border-radius: 36px;
        font-size: 26px;
    }
    QPushButton#dialBtn:hover { background-color: #f2f2f7; }

    QPushButton#callBtn {
        background-color: #34c759;
        border-radius: 38px;
        font-size: 22px;
        font-weight: 600;
        color: white;
    }

    QPushButton#backspaceBtn {
        background-color: #2c2c2e;
        border-radius: 22px;
        color: white;
        font-size: 18px;
    }
    QPushButton#backspaceBtn:hover {
        background-color: #3a3a3c;
    }

    QPushButton#miniBtn {
        background: transparent;
        border: none;
        color: #007aff;
        font-size: 14px;
    }
    """

    DARK_STYLE = """
    QWidget { background-color: #000000; color: #ffffff; }
    QLabel#dialDisplay { font-size: 34px; font-weight: 600; letter-spacing: 3px; }
    QLabel#status { color: #8e8e93; font-size: 13px; }

    QPushButton#dialBtn {
        background-color: #1c1c1e;
        border: 1px solid #2c2c2e;
        border-radius: 36px;
        font-size: 26px;
        color: white;
    }
    QPushButton#dialBtn:hover { background-color: #3a3a3c; }

    QPushButton#callBtn {
        background-color: #30d158;
        border-radius: 38px;
        font-size: 22px;
        font-weight: 600;
        color: black;
    }

    QPushButton#backspaceBtn {
        background-color: #2c2c2e;
        border-radius: 22px;
        color: white;
        font-size: 18px;
    }
    QPushButton#backspaceBtn:hover {
        background-color: #3a3a3c;
    }

    QPushButton#miniBtn {
        background: transparent;
        border: none;
        color: #0a84ff;
        font-size: 14px;
    }
    """

    is_dark = False
    dialer_page.setStyleSheet(LIGHT_STYLE)

    # ---------- TOP BAR ----------
    top_bar = QWidget()
    top_bar.setFixedHeight(44)

    top_layout = QHBoxLayout(top_bar)
    top_layout.setContentsMargins(0, 0, 0, 0)
    top_layout.setSpacing(8)

    dark_label = QLabel("DARK")
    light_label = QLabel("LIGHT")
    dark_label.setStyleSheet("color:#8e8e93; font-size:13px;")
    light_label.setStyleSheet("color:#8e8e93; font-size:13px;")

    switch = QPushButton()
    switch.setFixedSize(50, 26)
    switch.setCheckable(True)
    switch.setCursor(Qt.CursorShape.PointingHandCursor)
    switch.setStyleSheet("""
        QPushButton { background-color: #e5e5ea; border-radius: 13px; }
        QPushButton:checked { background-color: #34c759; }
    """)

    knob = QPushButton(switch)
    knob.setFixedSize(22, 22)
    knob.move(2, 2)
    knob.setEnabled(False)
    knob.setStyleSheet("background:white; border-radius:11px;")

    anim = QPropertyAnimation(knob, b"geometry")
    anim.setDuration(180)

    top_layout.addWidget(dark_label)
    top_layout.addWidget(switch)
    top_layout.addWidget(light_label)
    top_layout.addStretch()

    # settings and clear buttons removed

    layout.addWidget(top_bar)

    # ---------- DISPLAY ----------
    target_input = QLabel("")
    target_input.setObjectName("dialDisplay")
    target_input.setAlignment(Qt.AlignmentFlag.AlignHCenter)

    status_label = QLabel("Disconnected")
    status_label.setObjectName("status")
    status_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)

    display_box = QVBoxLayout()
    display_box.setSpacing(4)
    display_box.addWidget(target_input)
    display_box.addWidget(status_label)

    layout.addLayout(display_box)
    layout.addSpacing(16)

    # ---------- DIAL PAD ----------
    dialpad = QGridLayout()
    dialpad.setSpacing(18)

    for i, key in enumerate(["1","2","3","4","5","6","7","8","9","*","0","#"]):
        btn = QPushButton(key)
        btn.setFixedSize(76, 76)
        btn.setObjectName("dialBtn")
        btn.clicked.connect(lambda _, k=key: on_digit(k))
        dialpad.addWidget(btn, i//3, i%3)

    call_btn = QPushButton("Call")
    call_btn.setFixedSize(76, 76)
    call_btn.setObjectName("callBtn")
    call_btn.clicked.connect(on_call)

    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(24)
    shadow.setOffset(0, 6)
    shadow.setColor(QColor(0, 0, 0, 80))
    call_btn.setGraphicsEffect(shadow)

    backspace_btn = BackspaceButton("×")
    backspace_btn.setObjectName("backspaceBtn")

    long_press_fired = False
    clear_timer = QTimer()
    clear_timer.setSingleShot(True)
    clear_timer.setInterval(600)

    def on_backspace_press():
        nonlocal long_press_fired
        long_press_fired = False
        clear_timer.start()

    def on_backspace_release():
        nonlocal long_press_fired
        if clear_timer.isActive():
            clear_timer.stop()
        if not long_press_fired:
            on_backspace()

    def on_backspace_long_press():
        nonlocal long_press_fired
        long_press_fired = True
        on_clear()

    clear_timer.timeout.connect(on_backspace_long_press)
    backspace_btn.pressed.connect(on_backspace_press)
    backspace_btn.released.connect(on_backspace_release)

    dialpad.addWidget(call_btn, 4, 1, alignment=Qt.AlignmentFlag.AlignHCenter)
    dialpad.addWidget(backspace_btn, 4, 2, alignment=Qt.AlignmentFlag.AlignHCenter)

    pad_row = QHBoxLayout()
    pad_row.addStretch()
    pad_row.addLayout(dialpad)
    pad_row.addStretch()
    layout.addLayout(pad_row)

    # ---------- THEME TOGGLE ----------
    def toggle_theme_switch(checked):
        nonlocal is_dark
        is_dark = checked
        dialer_page.setStyleSheet(DARK_STYLE if is_dark else LIGHT_STYLE)

        if checked:
            anim.setStartValue(QRect(2, 2, 22, 22))
            anim.setEndValue(QRect(26, 2, 22, 22))
        else:
            anim.setStartValue(QRect(26, 2, 22, 22))
            anim.setEndValue(QRect(2, 2, 22, 22))
        anim.start()

    switch.toggled.connect(toggle_theme_switch)

    return dialer_page, target_input, status_label, call_btn
