import json
import math
import os
import pathlib
import threading
import wave
import winsound
import ctypes
import struct

from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QMainWindow, QStackedWidget, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton

from core.client_core import LanCallClient
from ui.pages.dialer import build_dialer_page
from ui.pages.incoming import build_incoming_page
from ui.pages.chat import build_chat_page
from ui.pages.incall import build_incall_page


APP_CONFIG_PATH = pathlib.Path(__file__).resolve().parents[1] / 'app_config.json'

DEFAULT_PRIMARY_NUMBER = "0650570453"
DEFAULT_SECONDARY_NUMBER = "0649408404"
DEFAULT_SERVER_IP = "127.0.0.1"
DEFAULT_LISTEN_PORT = 6000

# shared key (must match both clients)
KEY = b'DDbRDthATPBGP3yB2kjLto1Ph2un-lkYNaEklnyut3k='


def load_app_config():
    if not APP_CONFIG_PATH.exists():
        return {
            "server_ip": DEFAULT_SERVER_IP,
            "primary_number": DEFAULT_PRIMARY_NUMBER,
            "secondary_number": DEFAULT_SECONDARY_NUMBER,
            "listen_port": DEFAULT_LISTEN_PORT,
        }
    try:
        data = json.loads(APP_CONFIG_PATH.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            return {
                "server_ip": DEFAULT_SERVER_IP,
                "primary_number": DEFAULT_PRIMARY_NUMBER,
                "secondary_number": DEFAULT_SECONDARY_NUMBER,
                "listen_port": DEFAULT_LISTEN_PORT,
            }
        return {
            "server_ip": data.get("server_ip", DEFAULT_SERVER_IP),
            "primary_number": data.get("primary_number", DEFAULT_PRIMARY_NUMBER),
            "secondary_number": data.get("secondary_number", DEFAULT_SECONDARY_NUMBER),
            "listen_port": data.get("listen_port", DEFAULT_LISTEN_PORT),
        }
    except Exception:
        return {
            "server_ip": DEFAULT_SERVER_IP,
            "primary_number": DEFAULT_PRIMARY_NUMBER,
            "secondary_number": DEFAULT_SECONDARY_NUMBER,
            "listen_port": DEFAULT_LISTEN_PORT,
        }


def save_app_config(server_ip, primary_number, secondary_number, listen_port):
    data = {
        "server_ip": server_ip or DEFAULT_SERVER_IP,
        "primary_number": primary_number or DEFAULT_PRIMARY_NUMBER,
        "secondary_number": secondary_number or DEFAULT_SECONDARY_NUMBER,
        "listen_port": int(listen_port),
    }
    APP_CONFIG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def ensure_ringtone():
    mp3 = pathlib.Path(__file__).resolve().parents[1] / "yo_phone_linging.mp3"
    if mp3.exists():
        return str(mp3)

    path = pathlib.Path(__file__).resolve().parents[1] / "ringtone.wav"
    if path.exists():
        return str(path)

    rate = 22050
    duration = 0.35
    freq = 880.0
    frames = int(rate * duration)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        for i in range(frames):
            t = i / rate
            val = int(8000 * math.sin(2 * math.pi * freq * t))
            wf.writeframesraw(struct.pack("<h", val))
    return str(path)


class QtSignals(QObject):
    status = pyqtSignal(str)
    error = pyqtSignal(str)
    incoming = pyqtSignal(str)
    accepted = pyqtSignal(str)
    call_ready = pyqtSignal(str)
    question_received = pyqtSignal(str, str)
    answer_received = pyqtSignal(str, str)
    peer_approved = pyqtSignal(str)
    hangup = pyqtSignal(str)
    online = pyqtSignal(list)
    reg_in_use = pyqtSignal(str)


class ClientSignals:
    def __init__(self, qt_signals: QtSignals):
        self.status = qt_signals.status.emit
        self.error = qt_signals.error.emit
        self.incoming = qt_signals.incoming.emit
        self.accepted = qt_signals.accepted.emit
        self.call_ready = qt_signals.call_ready.emit
        self.question_received = qt_signals.question_received.emit
        self.answer_received = qt_signals.answer_received.emit
        self.peer_approved = qt_signals.peer_approved.emit
        self.hangup = qt_signals.hangup.emit
        self.online = qt_signals.online.emit
        self.reg_in_use = qt_signals.reg_in_use.emit


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # temporary placeholder; will set after primary_number is initialized
        self.setWindowTitle("Phone")
        self.setFixedSize(360, 640)

        self.qt_signals = QtSignals()
        self.signals = ClientSignals(self.qt_signals)
        self.client = LanCallClient(self.signals, KEY)
        self.pending_caller = None
        self.app_config = load_app_config()
        self.primary_number = self.app_config.get("primary_number", DEFAULT_PRIMARY_NUMBER)
        self.secondary_number = self.app_config.get("secondary_number", DEFAULT_SECONDARY_NUMBER)
        self.server_ip = self.app_config.get("server_ip", DEFAULT_SERVER_IP)
        self.listen_port = int(self.app_config.get("listen_port", DEFAULT_LISTEN_PORT))
        self.setWindowTitle(self.primary_number)
        self.ring_path = ensure_ringtone()
        self.ringing = False
        self.ring_is_mp3 = self.ring_path.lower().endswith(".mp3")
        self.ring_alias = f"ringtone_{os.getpid()}_{id(self)}"
        self.local_identity_approved = False
        self.peer_identity_approved = False
        self.local_question_sent = False
        self.remote_question_received = False
        self.local_answer_sent = False
        self.remote_answer_received = False

        font = QFont("Segoe UI", 10)
        self.setFont(font)
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                            stop:0 #eef3f6, stop:1 #f6f8f2);
            }
            QLabel#status {
                color: #6c7a86;
                font-size: 12px;
            }
            QLineEdit#dialDisplay {
                border: none;
                background: transparent;
                font-size: 28px;
                color: #3a3f44;
            }
            QPushButton#dialBtn {
                border: 2px solid #b9c3cc;
                color: #3f454b;
                border-radius: 32px;
                background: rgba(255, 255, 255, 0.6);
                font-size: 18px;
            }
            QPushButton#dialBtn:hover {
                background: rgba(255, 255, 255, 0.9);
            }
            QPushButton#callBtn {
                background: #6cc94e;
                color: white;
                border: none;
                border-radius: 32px;
                font-size: 18px;
            }
            QPushButton#callBtn:hover {
                background: #5bb542;
            }
            QPushButton#miniBtn {
                border: 1px solid #b9c3cc;
                background: rgba(255, 255, 255, 0.6);
                border-radius: 16px;
                color: #56606a;
            }
            QPushButton#acceptBtn {
                background: #6cc94e;
                color: white;
                border: none;
                border-radius: 14px;
            }
            QPushButton#hangupBtn {
                background: #e06565;
                color: white;
                border: none;
                border-radius: 14px;
            }
            QLabel#incomingName {
                font-size: 22px;
                color: #f2f5f7;
            }
            QLabel#incomingSub {
                font-size: 12px;
                color: #cbd3d8;
            }
            QPushButton#incomingAccept {
                background: #4cc06a;
                color: white;
                border: none;
                border-radius: 28px;
                font-size: 14px;
            }
            QPushButton#incomingDecline {
                background: #e05858;
                color: white;
                border: none;
                border-radius: 28px;
                font-size: 14px;
            }
            QLabel#inCallName {
                font-size: 20px;
                color: #f2f5f7;
            }
            QLabel#inCallTimer {
                font-size: 12px;
                color: #cbd3d8;
            }
            QPushButton#inCallBtn {
                border: none;
                border-radius: 28px;
                background: rgba(255, 255, 255, 0.12);
                color: #eef3f6;
            }
            QPushButton#inCallHangup {
                background: #e05858;
                color: white;
                border: none;
                border-radius: 30px;
            }
        """)

        dialer_page, self.target_input, self.status_label, self.call_btn = build_dialer_page(
            self.on_digit, self.on_call, self.on_backspace, self.on_clear, self.open_settings
        )

        incoming_page, self.incoming_name = build_incoming_page(self.on_accept, self.on_hangup)

        chat_page, self.chat_peer_label, self.chat_state_label, self.chat_question_input, self.chat_send_question_btn, self.chat_peer_question_label, self.chat_answer_input, self.chat_send_answer_btn, self.chat_peer_answer_label, self.chat_approve_btn = build_chat_page(
            self.on_send_question,
            self.on_send_answer,
            self.on_chat_approve,
            self.on_hangup,
        )

        in_call_page, self.in_call_name, self.in_call_timer, self.in_call_hangup = build_incall_page(self.on_hangup)

        self.pages = QStackedWidget()
        self.pages.addWidget(dialer_page)
        self.pages.addWidget(incoming_page)
        self.pages.addWidget(chat_page)
        self.pages.addWidget(in_call_page)
        self.PAGE_DIALER = 0
        self.PAGE_INCOMING = 1
        self.PAGE_CHAT = 2
        self.PAGE_INCALL = 3
        self.pages.setCurrentIndex(self.PAGE_DIALER)
        self.setCentralWidget(self.pages)

        self.call_timer = QTimer(self)
        self.call_timer.setInterval(1000)
        self.call_timer.timeout.connect(self._tick_call_timer)
        self.call_seconds = 0

        # connect signal slots (thread-safe)
        self.qt_signals.status.connect(self.set_status)
        self.qt_signals.error.connect(self.on_error)
        self.qt_signals.incoming.connect(self.on_incoming)
        self.qt_signals.accepted.connect(self.on_accepted)
        self.qt_signals.call_ready.connect(self.on_call_ready)
        self.qt_signals.question_received.connect(self.on_question_received)
        self.qt_signals.answer_received.connect(self.on_answer_received)
        self.qt_signals.peer_approved.connect(self.on_peer_approved)
        self.qt_signals.hangup.connect(self.on_hangup_msg)
        self.qt_signals.online.connect(self.on_online)
        self.qt_signals.reg_in_use.connect(self.on_reg_in_use)

        self._auto_connect_if_possible()

    def set_status(self, text):
        self.status_label.setText(text)

    def on_error(self, text):
        self.set_status(text)
        self._stop_ringtone()
        QMessageBox.warning(self, "Error", text)

    def on_incoming(self, caller):
        self.pending_caller = caller
        self.incoming_name.setText(caller)
        self.pages.setCurrentIndex(self.PAGE_INCOMING)
        self._start_ringtone()
        self.set_status(f"Incoming call from {caller}")

    def on_accepted(self, peer):
        self._open_chat(peer, local_approved=False, peer_approved=False)
        self.set_status(f"Connected to {peer}. Ask/answer question before approvals.")

    def on_call_ready(self, peer):
        self.in_call_name.setText(peer)
        self.pages.setCurrentIndex(self.PAGE_INCALL)
        self._stop_ringtone()
        self._start_call_timer()
        self.set_status(f"In call with {peer}")

    def on_hangup_msg(self, peer):
        self.pending_caller = None
        self._reset_chat_state()
        self._stop_ringtone()
        self._stop_call_timer()
        self.pages.setCurrentIndex(self.PAGE_DIALER)
        self.set_status(f"Call ended with {peer}")

    def on_reg_in_use(self, text):
        # Do not auto-switch; require manual config change
        self.on_error("ERROR IN_USE: number already registered. Change in app_config.json or Settings.")

    def on_online(self, numbers):
        pass

    def on_connect(self):
        host = self.server_ip
        my_number = self.primary_number
        listen_port = self.listen_port
        if not (my_number.isdigit() and len(my_number) == 10):
            QMessageBox.warning(self, "Invalid", "Your number must be exactly 10 digits")
            return
        if not (isinstance(listen_port, int) and 1 <= listen_port <= 65535):
            QMessageBox.warning(self, "Invalid", "Listen port must be 1-65535")
            return
        try:
            self.client.connect(host, 5000, my_number, listen_port)
            self.set_status("Connected")
            self.client.list_online()
        except Exception as e:
            QMessageBox.critical(self, "Connection failed", str(e))
            self.set_status("Disconnected")

    def _start_call_timer(self):
        self.call_seconds = 0
        self.in_call_timer.setText("00:00")
        self.call_timer.start()

    def _stop_call_timer(self):
        self.call_timer.stop()
        self.in_call_timer.setText("00:00")

    def _tick_call_timer(self):
        self.call_seconds += 1
        mm = self.call_seconds // 60
        ss = self.call_seconds % 60
        self.in_call_timer.setText(f"{mm:02d}:{ss:02d}")

    def _start_ringtone(self):
        if self.ringing:
            return
        try:
            if self.ring_is_mp3:
                path = os.path.abspath(self.ring_path)
                ctypes.windll.winmm.mciSendStringW(f"close {self.ring_alias}", None, 0, None)
                ctypes.windll.winmm.mciSendStringW(
                    f'open "{path}" type mpegvideo alias {self.ring_alias}', None, 0, None
                )
                ctypes.windll.winmm.mciSendStringW(f"play {self.ring_alias} repeat", None, 0, None)
            else:
                winsound.PlaySound(self.ring_path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
            self.ringing = True
        except Exception:
            pass

    def _stop_ringtone(self):
        if not self.ringing:
            return
        try:
            if self.ring_is_mp3:
                ctypes.windll.winmm.mciSendStringW(f"stop {self.ring_alias}", None, 0, None)
                ctypes.windll.winmm.mciSendStringW(f"close {self.ring_alias}", None, 0, None)
                ctypes.windll.winmm.mciSendStringW("stop all", None, 0, None)
                ctypes.windll.winmm.mciSendStringW("close all", None, 0, None)
            else:
                winsound.PlaySound(None, winsound.SND_ASYNC)
        finally:
            # fallback stop for any driver oddities
            try:
                winsound.PlaySound(None, winsound.SND_ASYNC)
            except Exception:
                pass
            self.ringing = False

    def _auto_connect_if_possible(self):
        my_number = self.primary_number
        if my_number.isdigit() and len(my_number) == 10:
            self.on_connect()
        else:
            self.set_status("Disconnected - enter your number")

    def open_settings(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Settings")
        dlg.setModal(True)

        layout = QVBoxLayout()

        ip_label = QLabel("Server IP")
        ip_input = QLineEdit(self.server_ip)
        layout.addWidget(ip_label)
        layout.addWidget(ip_input)

        primary_label = QLabel("Primary Number")
        primary_input = QLineEdit(self.primary_number)
        layout.addWidget(primary_label)
        layout.addWidget(primary_input)

        secondary_label = QLabel("Secondary Number")
        secondary_input = QLineEdit(self.secondary_number)
        layout.addWidget(secondary_label)
        layout.addWidget(secondary_input)

        port_label = QLabel("Listen Port")
        port_input = QLineEdit(str(self.listen_port))
        layout.addWidget(port_label)
        layout.addWidget(port_input)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        btn_row.addStretch(1)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        def on_save():
            self.server_ip = ip_input.text().strip() or DEFAULT_SERVER_IP
            self.primary_number = primary_input.text().strip() or DEFAULT_PRIMARY_NUMBER
            self.secondary_number = secondary_input.text().strip() or DEFAULT_SECONDARY_NUMBER
            try:
                self.listen_port = int(port_input.text().strip())
            except Exception:
                self.listen_port = DEFAULT_LISTEN_PORT
            if not (1 <= self.listen_port <= 65535):
                self.listen_port = DEFAULT_LISTEN_PORT

            self.setWindowTitle(self.primary_number)
            save_app_config(
                self.server_ip,
                self.primary_number,
                self.secondary_number,
                self.listen_port,
            )
            self.app_config = load_app_config()
            try:
                self.client.close()
            except Exception:
                pass
            self.on_connect()
            dlg.accept()

        save_btn.clicked.connect(on_save)
        cancel_btn.clicked.connect(dlg.reject)

        dlg.setLayout(layout)
        dlg.exec()

    def on_call(self):
        target = self.target_input.text().strip()
        if not (target.isdigit() and len(target) == 10):
            QMessageBox.warning(self, "Invalid", "Target must be exactly 10 digits")
            return
        threading.Thread(target=self.client.call, args=(target,), daemon=True).start()

    def on_accept(self):
        if self.pending_caller:
            self.client.accept(self.pending_caller)
            self._open_chat(self.pending_caller, local_approved=False, peer_approved=False)
            self._stop_ringtone()
            self.set_status(f"Connected to {self.pending_caller}. Ask/answer question before approvals.")

    def on_hangup(self):
        self.client.hangup()
        self.pending_caller = None
        self._reset_chat_state()
        self._stop_ringtone()
        self._stop_call_timer()
        self.pages.setCurrentIndex(self.PAGE_DIALER)
        self.set_status("Call ended")

    def on_refresh(self):
        self.client.list_online()

    def on_digit(self, ch: str):
        current = self.target_input.text()
        if len(current) >= 10:
            return
        if ch.isdigit():
            self.target_input.setText(current + ch)

    def on_backspace(self):
        current = self.target_input.text()
        if current:
            self.target_input.setText(current[:-1])

    def on_clear(self):
        self.target_input.clear()

    def on_send_question(self, text):
        question = (text or "").strip()
        if not question:
            return
        if self.local_question_sent:
            return
        self.client.send_question(question)
        self.local_question_sent = True
        self.chat_question_input.setEnabled(False)
        self.chat_send_question_btn.setEnabled(False)
        self.chat_question_input.setText(question)
        self._refresh_chat_state_label()

    def on_question_received(self, peer, text):
        self.remote_question_received = True
        self.chat_peer_question_label.setText(text or "-")
        self.chat_send_answer_btn.setEnabled(True)
        self.chat_answer_input.setEnabled(True)
        self._refresh_chat_state_label()

    def on_send_answer(self, text):
        answer = (text or "").strip()
        if not answer:
            return
        if self.local_answer_sent:
            return
        if not self.remote_question_received:
            return
        self.client.send_answer(answer)
        self.local_answer_sent = True
        self.chat_answer_input.setEnabled(False)
        self.chat_send_answer_btn.setEnabled(False)
        self.chat_answer_input.setText(answer)
        self._refresh_chat_state_label()

    def on_answer_received(self, peer, text):
        self.remote_answer_received = True
        self.chat_peer_answer_label.setText(f"Peer answer: {text or '-'}")
        self._refresh_chat_state_label()

    def on_chat_approve(self):
        if not self.local_answer_sent:
            return
        if self.local_identity_approved:
            return
        self.local_identity_approved = True
        self.chat_approve_btn.setEnabled(False)
        self.chat_approve_btn.setText("Approved")
        self.client.approve_identity()
        self._refresh_chat_state_label()

    def on_peer_approved(self, peer):
        self.peer_identity_approved = True
        self._refresh_chat_state_label()

    def _open_chat(self, peer, local_approved, peer_approved):
        self.chat_peer_label.setText(f"Peer: {peer}")
        self.local_identity_approved = local_approved
        self.peer_identity_approved = peer_approved
        self.local_question_sent = False
        self.remote_question_received = False
        self.local_answer_sent = False
        self.remote_answer_received = False
        self.chat_question_input.clear()
        self.chat_question_input.setEnabled(True)
        self.chat_send_question_btn.setEnabled(True)
        self.chat_peer_question_label.setText("-")
        self.chat_answer_input.clear()
        self.chat_answer_input.setEnabled(False)
        self.chat_send_answer_btn.setEnabled(False)
        self.chat_peer_answer_label.setText("Peer answer: -")
        self.chat_approve_btn.setEnabled(not local_approved)
        self.chat_approve_btn.setText("Approved" if local_approved else "Approve Identity")
        self._refresh_chat_state_label()
        self.pages.setCurrentIndex(self.PAGE_CHAT)

    def _refresh_chat_state_label(self):
        q_you = "sent" if self.local_question_sent else "pending your question"
        q_peer = "received" if self.remote_question_received else "waiting peer question"
        a_you = "sent" if self.local_answer_sent else "waiting your answer"
        approve_you = "approved" if self.local_identity_approved else "waiting your approval"
        approve_peer = "approved" if self.peer_identity_approved else "waiting peer approval"
        self.chat_state_label.setText(
            f"Your question: {q_you} | Peer question: {q_peer} | Your answer: {a_you} | You: {approve_you} | Peer: {approve_peer}"
        )
        can_approve = self.local_answer_sent and not self.local_identity_approved
        self.chat_approve_btn.setVisible(can_approve or self.local_identity_approved)
        if not self.local_identity_approved:
            self.chat_approve_btn.setEnabled(can_approve)

    def _reset_chat_state(self):
        self.local_identity_approved = False
        self.peer_identity_approved = False
        self.local_question_sent = False
        self.remote_question_received = False
        self.local_answer_sent = False
        self.remote_answer_received = False
        self.chat_peer_label.setText("Peer: -")
        self.chat_state_label.setText("Ask one question, answer the peer question, then approve identity.")
        self.chat_question_input.clear()
        self.chat_question_input.setEnabled(True)
        self.chat_send_question_btn.setEnabled(True)
        self.chat_peer_question_label.setText("-")
        self.chat_answer_input.clear()
        self.chat_answer_input.setEnabled(False)
        self.chat_send_answer_btn.setEnabled(False)
        self.chat_peer_answer_label.setText("Peer answer: -")
        self.chat_approve_btn.setVisible(False)
        self.chat_approve_btn.setEnabled(False)
        self.chat_approve_btn.setText("Approve Identity")

