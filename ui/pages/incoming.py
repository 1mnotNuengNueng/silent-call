from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QColor

def build_incoming_page(on_accept, on_decline):
    page = QWidget()
    
    # --- Stylesheet: iOS Light Theme ---
    page.setStyleSheet("""
        QWidget {
            background-color: #FFFFFF;
            font-family: -apple-system, Inter, Segoe UI, sans-serif;
        }

        /* ชื่อคนโทรเข้า ตัวใหญ่ชัดเจน */
        QLabel#incomingName {
            font-size: 38px;
            font-weight: 400; /* iOS มักใช้ฟอนต์บางลงนิดหน่อยสำหรับชื่อ */
            color: #000000;
        }

        /* ข้อความสถานะ (iPhone, Mobile...) */
        QLabel#incomingSub {
            font-size: 20px;
            color: #8e8e93; /* สีเทา */
            margin-top: 5px;
        }

        /* ข้อความใต้ปุ่ม (Decline / Accept) */
        QLabel#actionLabel {
            font-size: 14px;
            color: #000000;
            font-weight: 500;
        }

        /* ปุ่มวงกลม */
        QPushButton {
            border-radius: 40px; /* ครึ่งหนึ่งของขนาด 80px */
            font-size: 32px;
            color: white;
            border: none;
        }

        /* ปุ่มปฏิเสธ (สีแดง) */
        QPushButton#btnDecline {
            background-color: #FF3B30;
        }
        QPushButton#btnDecline:hover {
            background-color: #FF453A;
        }
        QPushButton#btnDecline:pressed {
            background-color: #D70015;
        }

        /* ปุ่มรับสาย (สีเขียว) */
        QPushButton#btnAccept {
            background-color: #34C759;
        }
        QPushButton#btnAccept:hover {
            background-color: #46D869;
        }
        QPushButton#btnAccept:pressed {
            background-color: #248A3D;
        }
    """)

    main_layout = QVBoxLayout(page)
    main_layout.setContentsMargins(32, 60, 32, 60)

    # ------------------------------------
    # ส่วนบน: ข้อมูลคนโทรเข้า
    # ------------------------------------
    main_layout.addStretch(2)

    name_label = QLabel("Unknown")
    name_label.setObjectName("incomingName")
    name_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    main_layout.addWidget(name_label)

    sub_label = QLabel("iPhone")
    sub_label.setObjectName("incomingSub")
    sub_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    main_layout.addWidget(sub_label)

    main_layout.addStretch(3)

    # ------------------------------------
    # ส่วนล่าง: ปุ่มกด (จัดแบบ Grid แนวนอน)
    # ------------------------------------
    
    # เราจะสร้าง Helper function เล็กๆ เพื่อสร้างปุ่มพร้อมข้อความใต้ปุ่ม
    def create_action_button(icon_text, label_text, obj_name, callback):
        container = QWidget()
        v_layout = QVBoxLayout(container)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(10) # ระยะห่างระหว่างปุ่มกับตัวหนังสือ

        # ตัวปุ่ม
        btn = QPushButton(icon_text)
        btn.setObjectName(obj_name)
        btn.setFixedSize(80, 80) # ขนาดปุ่มวงกลม
        
        # เพิ่มเงาให้ปุ่มดูมีมิติ
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 4)
        btn.setGraphicsEffect(shadow)
        
        btn.clicked.connect(callback)

        # ตัวหนังสือใต้ปุ่ม
        lbl = QLabel(label_text)
        lbl.setObjectName("actionLabel")
        lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        v_layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        v_layout.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignHCenter)
        
        return container

    # สร้าง Layout แนวนอนสำหรับปุ่ม
    buttons_layout = QHBoxLayout()
    buttons_layout.setSpacing(60) # ระยะห่างระหว่างปุ่มซ้ายขวา
    buttons_layout.addStretch(1)

    # ปุ่ม Decline (ซ้าย)
    # ใช้ไอคอนกากบาท หรือสัญลักษณ์โทรศัพท์คว่ำ
    decline_widget = create_action_button("✕", "Decline", "btnDecline", on_decline)
    buttons_layout.addWidget(decline_widget)

    # ปุ่ม Accept (ขวา)
    # ใช้ไอคอนโทรศัพท์
    accept_widget = create_action_button("📞", "Accept", "btnAccept", on_accept)
    buttons_layout.addWidget(accept_widget)

    buttons_layout.addStretch(1)

    main_layout.addLayout(buttons_layout)
    main_layout.addSpacing(40) # เว้นระยะจากขอบล่างอีกนิด

    return page, name_label