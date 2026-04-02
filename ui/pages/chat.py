from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QFrame,
)


def build_chat_page(on_send_question, on_send_answer, on_approve, on_hangup):
    page = QWidget()
    page.setStyleSheet(
        """
        QWidget {
            background-color: #f5f7fb;
            font-family: "Segoe UI", sans-serif;
        }

        QLabel#title {
            font-size: 24px;
            font-weight: 700;
            color: #111111;
        }

        QLabel#sub {
            font-size: 13px;
            color: #6e6e73;
        }

        QLabel#cardTitle {
            font-size: 14px;
            font-weight: 600;
            color: #1c1c1e;
        }

        QFrame#card {
            background: #ffffff;
            border-radius: 16px;
            padding: 16px;
        }

        QLabel#peerQuestion {
            background: #f2f2f7;
            border-radius: 10px;
            padding: 10px;
            font-size: 13px;
            color: #111;
        }

        QLineEdit#input {
            border: 1px solid #d1d1d6;
            border-radius: 10px;
            padding: 10px;
            font-size: 13px;
            background: #ffffff;
        }

        QLineEdit#input:focus {
            border: 1px solid #2f80ed;
        }

        QPushButton#primary {
            background: #2f80ed;
            color: white;
            border-radius: 10px;
            padding: 8px 14px;
            font-weight: 500;
        }

        QPushButton#primary:hover {
            background: #1f6fe0;
        }

        QPushButton#approve {
            background: #34c759;
            color: white;
            border-radius: 12px;
            padding: 12px;
            font-weight: 600;
        }

        QPushButton#approve:hover {
            background: #28b74f;
        }

        QPushButton#hangup {
            background: #ff3b30;
            color: white;
            border-radius: 12px;
            padding: 12px;
            font-weight: 600;
        }

        QPushButton#hangup:hover {
            background: #e02d24;
        }
        """
    )

    layout = QVBoxLayout(page)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)

    title = QLabel("Identity Verification")
    title.setObjectName("title")
    title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    layout.addWidget(title)

    peer_label = QLabel("Peer: -")
    peer_label.setObjectName("sub")
    peer_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    layout.addWidget(peer_label)

    status_label = QLabel("Ask a shared question, answer the peer, then approve identity.")
    status_label.setObjectName("sub")
    status_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    layout.addWidget(status_label)

    card = QFrame()
    card.setObjectName("card")
    card_layout = QVBoxLayout(card)
    card_layout.setSpacing(14)

    my_q_title = QLabel("Your question")
    my_q_title.setObjectName("cardTitle")
    card_layout.addWidget(my_q_title)

    my_q_row = QHBoxLayout()
    my_question_input = QLineEdit()
    my_question_input.setObjectName("input")
    my_question_input.setPlaceholderText("Type one verification question...")
    send_question_btn = QPushButton("Send")
    send_question_btn.setObjectName("primary")
    my_q_row.addWidget(my_question_input, 1)
    my_q_row.addWidget(send_question_btn)
    card_layout.addLayout(my_q_row)

    peer_q_title = QLabel("Peer question")
    peer_q_title.setObjectName("cardTitle")
    card_layout.addWidget(peer_q_title)

    peer_question_label = QLabel("-")
    peer_question_label.setObjectName("peerQuestion")
    peer_question_label.setWordWrap(True)
    card_layout.addWidget(peer_question_label)

    my_a_title = QLabel("Your answer")
    my_a_title.setObjectName("cardTitle")
    card_layout.addWidget(my_a_title)

    my_a_row = QHBoxLayout()
    my_answer_input = QLineEdit()
    my_answer_input.setObjectName("input")
    my_answer_input.setPlaceholderText("Type your answer...")
    send_answer_btn = QPushButton("Send")
    send_answer_btn.setObjectName("primary")
    my_a_row.addWidget(my_answer_input, 1)
    my_a_row.addWidget(send_answer_btn)
    card_layout.addLayout(my_a_row)

    peer_answer_label = QLabel("Peer answer: -")
    peer_answer_label.setObjectName("sub")
    peer_answer_label.setWordWrap(True)
    card_layout.addWidget(peer_answer_label)

    layout.addWidget(card)
    layout.addStretch()

    action_row = QHBoxLayout()
    action_row.setSpacing(12)

    approve_btn = QPushButton("Approve Identity")
    approve_btn.setObjectName("approve")

    hangup_btn = QPushButton("Hang up")
    hangup_btn.setObjectName("hangup")

    action_row.addWidget(approve_btn)
    action_row.addWidget(hangup_btn)
    layout.addLayout(action_row)

    def emit_question():
        text = my_question_input.text().strip()
        if text:
            on_send_question(text)

    def emit_answer():
        text = my_answer_input.text().strip()
        if text:
            on_send_answer(text)

    send_question_btn.clicked.connect(emit_question)
    my_question_input.returnPressed.connect(emit_question)
    send_answer_btn.clicked.connect(emit_answer)
    my_answer_input.returnPressed.connect(emit_answer)
    approve_btn.clicked.connect(on_approve)
    hangup_btn.clicked.connect(on_hangup)

    return (
        page,
        peer_label,
        status_label,
        my_question_input,
        send_question_btn,
        peer_question_label,
        my_answer_input,
        send_answer_btn,
        peer_answer_label,
        approve_btn,
    )
