import os
import socket
import struct
import threading
import time
import base64

try:
    import pyaudio
except ModuleNotFoundError:
    import pyaudiowpatch as pyaudio
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


class ClientSignals:
    def __init__(self):
        self.status = None
        self.error = None
        self.incoming = None
        self.accepted = None
        self.call_ready = None
        self.question_received = None
        self.answer_received = None
        self.peer_approved = None
        self.hangup = None
        self.online = None
        self.reg_in_use = None


class LanCallClient:
    def __init__(self, signals, key: bytes):
        # UI callbacks / event hooks (set by UI layer)
        self.signals = signals
        self.signal_host = None
        self.signal_port = None
        self.listen_port = None
        self.my_number = None

        # Incoming peer connection listener
        self.listen_sock = None
        self.listen_thread = None

        # Active peer connection (call media channel)
        self.peer_sock = None
        self.peer_lock = threading.Lock()
        self.peer_number = None

        # Call/session state
        self.lock = threading.Lock()
        self.in_call = threading.Event()
        self.stop_flag = threading.Event()
        self.audio = None
        self.stream_in = None
        self.stream_out = None
        self.receiver_thread = None
        self.sender_thread = None
        self.connected = False

        # Crypto state (X25519 key exchange + AES-GCM audio)
        self.key_salt = key or None
        self.local_priv = None
        self.local_pub = None
        self.peer_pub = None
        self.aesgcm = None
        self.key_ready = threading.Event()
        self.last_rekey = 0.0
        self.rekey_interval = 30.0
        self.rekey_overlap = 10.0
        self.debug_crypto = True
        self.is_caller = None
        self.prev_aesgcm = None
        self.prev_key_until = 0.0
        self.connect_timeout = 3.0
        self.local_approved = False
        self.remote_approved = False

    def connect(self, host, port, my_number, listen_port):
        # Initialize audio + background threads and register with signaling server
        self.signal_host = host
        self.signal_port = port
        self.listen_port = listen_port
        self.connected = True
        self.my_number = my_number

        self.audio = pyaudio.PyAudio()
        self.stream_in = self.audio.open(format=pyaudio.paInt16,
                                         channels=1,
                                         rate=22050,
                                         input=True,
                                         frames_per_buffer=1024)
        self.stream_out = self.audio.open(format=pyaudio.paInt16,
                                          channels=1,
                                          rate=22050,
                                          output=True,
                                          frames_per_buffer=1024)

        self.stop_flag.clear()
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.receiver_thread = threading.Thread(target=self._receiver_loop, daemon=True)
        self.sender_thread = threading.Thread(target=self._sender_loop, daemon=True)
        self.listen_thread.start()
        self.receiver_thread.start()
        self.sender_thread.start()

        self._register_with_server()
        self._emit(self.signals.status, "Registered")

    def close(self):
        # Stop all threads, close sockets, and release audio resources
        self.stop_flag.set()
        try:
            if self.listen_sock:
                self.listen_sock.close()
        except Exception:
            pass
        try:
            with self.peer_lock:
                if self.peer_sock:
                    self.peer_sock.close()
                    self.peer_sock = None
        except Exception:
            pass
        self._clear_session_keys()
        try:
            if self.stream_in:
                self.stream_in.close()
            if self.stream_out:
                self.stream_out.close()
            if self.audio:
                self.audio.terminate()
        except Exception:
            pass
        self.connected = False
        self.in_call.clear()

    def send_frame(self, msg_type: bytes, payload: bytes):
        # Send a framed message on the peer socket (C=control, K=key, A=audio)
        with self.peer_lock:
            if not self.peer_sock:
                raise RuntimeError("No peer connection")
            header = msg_type + struct.pack("!I", len(payload))
            try:
                self.peer_sock.sendall(header + payload)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                if self.debug_crypto:
                    print("[net] send_frame failed: peer socket error, closing connection")
                try:
                    self.peer_sock.close()
                except Exception:
                    pass
                self.peer_sock = None
                self.in_call.clear()
                self._emit(self.signals.hangup, self.peer_number or "")
                self._emit(self.signals.error, "ERROR CONNECTION_LOST")
                raise

    def send_control(self, text: str):
        # Send a control string over the peer connection
        try:
            self.send_frame(b"C", text.encode("utf-8"))
        except RuntimeError:
            self._emit(self.signals.error, "ERROR CONNECTION_LOST")

    def send_question(self, text: str):
        # Send one identity-check question to peer
        question = (text or "").strip()
        if not question:
            return
        with self.peer_lock:
            if not self.peer_sock:
                self._emit(self.signals.error, "ERROR CONNECTION_LOST")
                return
        enc = self._encrypt_secure_text(question)
        if not enc:
            self._emit(self.signals.error, "ERROR SECURE_CHANNEL_NOT_READY")
            return
        self.send_control(f"QASKENC {enc}")

    def send_answer(self, text: str):
        # Send answer to peer's question
        answer = (text or "").strip()
        if not answer:
            return
        with self.peer_lock:
            if not self.peer_sock:
                self._emit(self.signals.error, "ERROR CONNECTION_LOST")
                return
        enc = self._encrypt_secure_text(answer)
        if not enc:
            self._emit(self.signals.error, "ERROR SECURE_CHANNEL_NOT_READY")
            return
        self.send_control(f"QANSENC {enc}")

    def approve_identity(self):
        # Local user approves peer identity; call starts when both sides approve
        if self.local_approved:
            return
        with self.peer_lock:
            if not self.peer_sock:
                self._emit(self.signals.error, "ERROR CONNECTION_LOST")
                return
        self.local_approved = True
        self.send_control(f"APPROVE {self.my_number}")
        self._try_enter_call()

    def call(self, target):
        # Outgoing call: ask signaling server for peer, connect, then send CALL
        if not self.connected:
            return
        peer = self._lookup_peer(target)
        if not peer:
            self._emit(self.signals.error, "ERROR OFFLINE")
            return
        ip, port = peer
        if not self._connect_peer(ip, port):
            self._emit(self.signals.error, "ERROR CONNECT")
            return
        with self.peer_lock:
            if not self.peer_sock:
                self._emit(self.signals.error, "ERROR CONNECTION_LOST")
                return
        self.peer_number = target
        self.is_caller = True
        if self.debug_crypto:
            print(f"[net] calling {target} at {ip}:{port}")
        self.send_control(f"CALL {self.my_number}")
        self._emit(self.signals.status, f"Calling {target}...")

    def accept(self, caller):
        # Accept incoming call and move both peers to chat approval step
        self.peer_number = caller
        self.is_caller = False
        self.local_approved = False
        self.remote_approved = False
        if self.debug_crypto:
            print(f"[net] accepting call from {caller}")
        self.send_control(f"ACCEPT {self.my_number}")

    def hangup(self):
        # Accept incoming call and mark in-call state???????
        try:
            self.send_control(f"HANGUP {self.my_number}")
        except Exception:
            pass
        self.in_call.clear()
        if self.debug_crypto:
            print("[net] hangup requested, closing peer")
        self._close_peer()
        self.is_caller = None

    def list_online(self):
        # Not implemented in current signaling server
        pass

    def _recv_full(self, sock, size):
        # Read exactly size bytes from socket (or None on error/closed)
        data = b""
        while len(data) < size:
            try:
                packet = sock.recv(size - len(data))
            except (ConnectionResetError, OSError):
                if self.debug_crypto:
                    print("[net] recv_full failed: socket error")
                return None
            if not packet:
                if self.debug_crypto:
                    print("[net] recv_full failed: peer closed connection")
                return None
            data += packet
        return data

    def _recv_frame(self, sock):
        # Read a framed message: [1-byte type][4-byte length][payload]
        header = self._recv_full(sock, 5)
        if not header:
            return None, None
        msg_type = header[:1]
        size = struct.unpack("!I", header[1:])[0]
        payload = self._recv_full(sock, size)
        if payload is None:
            return None, None
        return msg_type, payload

    def _emit(self, slot, *values):
        # Safe UI callback invocation (ignore UI exceptions)
        try:
            if slot:
                slot(*values)
        except Exception:
            pass

    def _receiver_loop(self):
        # Peer receive loop: control, key exchange, and audio playback
        try:
            while not self.stop_flag.is_set():
                with self.peer_lock:
                    peer = self.peer_sock
                if not peer:
                    time.sleep(0.05)
                    continue

                msg_type, payload = self._recv_frame(peer)
                if msg_type is None:
                    if self.peer_number:
                        self.in_call.clear()
                        self._emit(self.signals.hangup, self.peer_number)
                    self._close_peer()
                    continue

                if msg_type == b"C":
                    text = payload.decode("utf-8", errors="replace")
                    if self.debug_crypto:
                        print(f"[net] control msg: {text}")
                    if text.startswith("CALL "):
                        caller = text.split(" ", 1)[1]
                        self.peer_number = caller
                        self._emit(self.signals.incoming, caller)
                    elif text.startswith("ACCEPT "):
                        peer_num = text.split(" ", 1)[1]
                        self.peer_number = peer_num
                        self.local_approved = False
                        self.remote_approved = False
                        self._emit(self.signals.accepted, peer_num)
                    elif text.startswith("QASKENC "):
                        _, _, enc = text.partition(" ")
                        question = self._decrypt_secure_text(enc)
                        if question is None:
                            self._emit(self.signals.error, "ERROR QUESTION_DECRYPT")
                            continue
                        self._emit(self.signals.question_received, self.peer_number or "", question)
                    elif text.startswith("QANSENC "):
                        _, _, enc = text.partition(" ")
                        answer = self._decrypt_secure_text(enc)
                        if answer is None:
                            self._emit(self.signals.error, "ERROR ANSWER_DECRYPT")
                            continue
                        self._emit(self.signals.answer_received, self.peer_number or "", answer)
                    elif text.startswith("APPROVE "):
                        _, _, peer_num = text.partition(" ")
                        self.remote_approved = True
                        self._emit(self.signals.peer_approved, peer_num)
                        self._try_enter_call()
                    elif text.startswith("HANGUP "):
                        peer_num = text.split(" ", 1)[1]
                        self.in_call.clear()
                        self._emit(self.signals.hangup, peer_num)
                        self._close_peer()
                    elif text == "HANGUP":
                        self.in_call.clear()
                        self._emit(self.signals.hangup, self.peer_number or "")
                        self._close_peer()
                    elif text.startswith("ERROR "):
                        self._emit(self.signals.error, text)

                elif msg_type == b"K":
                    if payload:
                        try:
                            self.peer_pub = x25519.X25519PublicKey.from_public_bytes(payload)
                            self._derive_session_key()
                        except Exception:
                            self._emit(self.signals.error, "ERROR KEY_EXCHANGE")

                elif msg_type == b"A":
                    if self.in_call.is_set():
                        decrypted = self._decrypt_audio(payload)
                        if decrypted is None:
                            if self.debug_crypto:
                                print("[audio] decrypt failed or key not ready")
                            continue
                        try:
                            self.stream_out.write(decrypted)
                        except Exception as e:
                            if self.debug_crypto:
                                print(f"[audio] output write failed: {e}")
        except Exception as e:
            if self.debug_crypto:
                print(f"[net] receiver_loop exception: {e}")
        finally:
            if self.debug_crypto:
                print("[net] receiver_loop exiting")
            self.stop_flag.set()

    def _sender_loop(self):
        # Microphone read loop + encrypt/send audio frames
        try:
            while not self.stop_flag.is_set():
                if self.peer_sock and (time.time() - self.last_rekey) >= self.rekey_interval:
                    if self.in_call.is_set() and self.is_caller:
                        self._rotate_local_key()
                try:
                    data = self.stream_in.read(1024, exception_on_overflow=False)
                except Exception as e:
                    if self.debug_crypto:
                        print(f"[audio] input read failed: {e}")
                    break
                if self.in_call.is_set() and self.key_ready.is_set():
                    try:
                        nonce = os.urandom(12)
                        encrypted = self.aesgcm.encrypt(nonce, data, None)
                        if self.debug_crypto:
                            print(f"[crypto] encrypting audio with session key id={self._key_id}")
                        self.send_frame(b"A", nonce + encrypted)
                    except Exception as e:
                        if self.debug_crypto:
                            print(f"[net] sender_loop exception: {e}")
                        break
                else:
                    time.sleep(0.01)
        except Exception as e:
            if self.debug_crypto:
                print(f"[net] sender_loop outer exception: {e}")
        finally:
            if self.debug_crypto:
                print("[net] sender_loop exiting")

    def _listen_loop(self):
        # Accept incoming call and mark in-call state?? listen_port
        self.listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.listen_sock.bind(("0.0.0.0", self.listen_port))
        except Exception as e:
            if self.debug_crypto:
                print(f"[net] listen bind failed on {self.listen_port}: {e}")
            return
        self.listen_sock.listen(1)
        while not self.stop_flag.is_set():
            try:
                conn, _ = self.listen_sock.accept()
            except Exception:
                if self.debug_crypto:
                    print("[net] listen_loop stopped: accept failed")
                break
            if self.in_call.is_set() or self.peer_sock is not None:
                try:
                    conn.close()
                except Exception:
                    pass
                continue
            self._set_peer(conn)

    def _connect_peer(self, ip, port):
        # Connect to peer's listening socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.connect_timeout)
            sock.connect((ip, port))
            # reset to blocking mode for long-lived call
            sock.settimeout(None)
        except Exception:
            if self.debug_crypto:
                print(f"[net] connect_peer failed: {ip}:{port}")
            return False
        self._set_peer(sock)
        return True

    def _set_peer(self, sock):
        # Install peer socket and start key exchange
        with self.peer_lock:
            if self.peer_sock:
                try:
                    self.peer_sock.close()
                except Exception:
                    pass
            self.peer_sock = sock
        if self.debug_crypto:
            try:
                addr = sock.getpeername()
            except Exception:
                addr = ("?", "?")
            print(f"[net] peer socket set: {addr}")
        self._init_session_keys()
        self._send_key()

    def _close_peer(self):
        # Close peer socket and clear session state
        with self.peer_lock:
            if self.peer_sock:
                try:
                    self.peer_sock.close()
                except Exception:
                    pass
            self.peer_sock = None
        if self.debug_crypto:
            print("[net] peer socket closed")
        self.peer_number = None
        self.local_approved = False
        self.remote_approved = False
        self._clear_session_keys()
        self.is_caller = None

    def _init_session_keys(self):
        # Create new local X25519 keypair and reset crypto state
        self.local_priv = x25519.X25519PrivateKey.generate()
        self.local_pub = self.local_priv.public_key()
        self.peer_pub = None
        self.aesgcm = None
        self.key_ready.clear()
        self.last_rekey = time.time()
        self.local_approved = False
        self.remote_approved = False

    def _clear_session_keys(self):
        # Clear all crypto material
        self.local_priv = None
        self.local_pub = None
        self.peer_pub = None
        self.aesgcm = None
        self.prev_aesgcm = None
        self.prev_key_until = 0.0
        self.key_ready.clear()
        self.last_rekey = 0.0

    def _rotate_local_key(self):
        # Accept incoming call and mark in-call state????
        if not self.peer_sock:
            return
        self.local_priv = x25519.X25519PrivateKey.generate()
        self.local_pub = self.local_priv.public_key()
        self.last_rekey = time.time()
        self._send_key()
        if self.peer_pub:
            self._derive_session_key()

    def _send_key(self):
        # Send our public key to peer
        if not self.local_pub:
            return
        try:
            pub_bytes = self.local_pub.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            self.send_frame(b"K", pub_bytes)
        except Exception:
            pass

    def _derive_session_key(self):
        # Derive AES-GCM key using X25519 + HKDF
        if not (self.local_priv and self.peer_pub):
            return
        shared = self.local_priv.exchange(self.peer_pub)
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.key_salt,
            info=b"lan-call-aesgcm",
        )
        key = hkdf.derive(shared)
        if self.aesgcm:
            self.prev_aesgcm = self.aesgcm
            self.prev_key_until = time.time() + self.rekey_overlap
        self.aesgcm = AESGCM(key)
        self.key_ready.set()
        self.last_rekey = time.time()
        self._key_id = key.hex()[:16]
        if self.debug_crypto:
            print(f"[crypto] session key ready id={self._key_id}")


    def _decrypt_audio(self, payload):
        # Send a control string over the peer connection?
        if len(payload) < 13:
            return None
        nonce = payload[:12]
        ciphertext = payload[12:]
        if self.aesgcm and self.key_ready.is_set():
            try:
                return self.aesgcm.decrypt(nonce, ciphertext, None)
            except Exception:
                pass
        if self.prev_aesgcm and time.time() <= self.prev_key_until:
            try:
                return self.prev_aesgcm.decrypt(nonce, ciphertext, None)
            except Exception:
                pass
        return None

    def _try_enter_call(self):
        # Start audio only after both peers approved identity in chat
        if self.local_approved and self.remote_approved and not self.in_call.is_set():
            self.in_call.set()
            self._emit(self.signals.call_ready, self.peer_number or "")

    def _encrypt_secure_text(self, plaintext: str):
        # Encrypt short control payloads (Q/A verify step) using current session key
        if not plaintext:
            return None
        if not self.key_ready.wait(timeout=3.0):
            return None
        if not self.aesgcm:
            return None
        try:
            nonce = os.urandom(12)
            encrypted = self.aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
            return base64.urlsafe_b64encode(nonce + encrypted).decode("ascii")
        except Exception:
            return None

    def _decrypt_secure_text(self, encoded: str):
        # Decrypt short control payloads with active key, fallback previous key during rekey overlap
        if not encoded:
            return None
        try:
            raw = base64.urlsafe_b64decode(encoded.encode("ascii"))
        except Exception:
            return None
        if len(raw) < 13:
            return None
        nonce = raw[:12]
        ciphertext = raw[12:]
        if self.aesgcm and self.key_ready.is_set():
            try:
                return self.aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8", errors="replace")
            except Exception:
                pass
        if self.prev_aesgcm and time.time() <= self.prev_key_until:
            try:
                return self.prev_aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8", errors="replace")
            except Exception:
                pass
        return None

    def _register_with_server(self):
        # Accept incoming call and mark in-call state? signaling server
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.connect_timeout)
            sock.connect((self.signal_host, self.signal_port))
            sock.send(f"{self.my_number}|{self.listen_port}|".encode())
            sock.recv(1024)
            sock.close()
        except Exception:
            pass

    def _lookup_peer(self, target):
        # Ask signaling server for target's IP/port
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.connect_timeout)
            sock.connect((self.signal_host, self.signal_port))
            sock.send(f"{self.my_number}|{self.listen_port}|{target}".encode())
            resp = sock.recv(1024).decode(errors="replace")
            sock.close()
        except Exception:
            return None
        if resp.startswith("PEER|"):
            parts = resp.split("|")
            if len(parts) >= 3:
                return parts[1], int(parts[2])
        return None
