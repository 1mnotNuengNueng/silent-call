from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout,
    QLabel, QPushButton, QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QColor

def build_incall_page(on_hangup):
    page = QWidget()
    
    # --- Stylesheet: Clean Minimal ---
    page.setStyleSheet("""
        QWidget {
            background-color: #FFFFFF;
            font-family: -apple-system, "Segoe UI", sans-serif;
        }

        /* --- Header Text --- */
        QLabel#callState {
            font-size: 16px;
            color: #8E8E93;
            margin-bottom: 5px;
        }
        QLabel#callNumber {
            font-size: 38px;
            font-weight: 600;
            color: #000000;
            letter-spacing: 0.5px;
        }
        QLabel#callTimer {
            font-size: 20px;
            color: #8E8E93;
            margin-top: 5px;
        }

        /* --- Hangup Button (Red) --- */
        QPushButton#hangupBtn {
            background-color: #FF3B30;
            border-radius: 40px; /* ครึ่งของขนาด 80px */
            font-size: 32px;
            color: white;
            border: none;
        }
        QPushButton#hangupBtn:hover {
            background-color: #FF453A;
        }
        QPushButton#hangupBtn:pressed {
            background-color: #D70015;
        }
    """)

    layout = QVBoxLayout(page)
    layout.setContentsMargins(30, 60, 30, 80) # เพิ่มขอบล่างเยอะหน่อยให้ปุ่มลอยสูงขึ้นมานิดนึง

    # ------------------------------------
    # ส่วนบน: ข้อมูลการโทร
    # ------------------------------------
    layout.addStretch(1)
    
    state_label = QLabel("กำลังโทร...") 
    state_label.setObjectName("callState")
    state_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    layout.addWidget(state_label)

    number_label = QLabel("092-469-3659")
    number_label.setObjectName("callNumber")
    number_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    layout.addWidget(number_label)

    timer_label = QLabel("ไทย")
    timer_label.setObjectName("callTimer")
    timer_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    layout.addWidget(timer_label)

    # ------------------------------------
    # พื้นที่ว่างตรงกลาง (ดันปุ่มวางสายลงไปข้างล่าง)
    # ------------------------------------
    layout.addStretch(3)

    # ------------------------------------
    # ส่วนล่าง: ปุ่มวางสาย
    # ------------------------------------
    hangup_btn = QPushButton("📞") # ไอคอนหูโทรศัพท์
    hangup_btn.setObjectName("hangupBtn")
    hangup_btn.setFixedSize(80, 80)
    hangup_btn.clicked.connect(on_hangup)

    # ใส่เงาให้ปุ่มดูมีมิติ
    hangup_shadow = QGraphicsDropShadowEffect()
    hangup_shadow.setBlurRadius(25)
    hangup_shadow.setOffset(0, 8)
    hangup_shadow.setColor(QColor(0, 0, 0, 70)) # เงาสีดำจางๆ
    hangup_btn.setGraphicsEffect(hangup_shadow)

    layout.addWidget(hangup_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
    
    # ดันขึ้นมาจากขอบล่างนิดหน่อย ไม่ให้ชิดเกินไป
    layout.addSpacing(20) 

    return page, number_label, timer_label, hangup_btn