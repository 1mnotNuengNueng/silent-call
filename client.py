import socket
import pyaudio
import struct
import threading

HOST = input("Enter server IP: ")
PORT = 5000

my_number = input("Enter your 10-digit number: ").strip()
if not (my_number.isdigit() and len(my_number) == 10):
    raise SystemExit("Number must be exactly 10 digits")

target_number = input("Call which 10-digit number? ").strip()
if not (target_number.isdigit() and len(target_number) == 10):
    raise SystemExit("Target must be exactly 10 digits")

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((HOST, PORT))


def send_frame(msg_type: bytes, payload: bytes):
    header = msg_type + struct.pack("!I", len(payload))
    sock.sendall(header + payload)


def recv_full(size):
    data = b""
    while len(data) < size:
        packet = sock.recv(size - len(data))
        if not packet:
            return None
        data += packet
    return data


def recv_frame():
    header = recv_full(5)
    if not header:
        return None, None
    msg_type = header[:1]
    size = struct.unpack("!I", header[1:])[0]
    payload = recv_full(size)
    if payload is None:
        return None, None
    return msg_type, payload


# register
send_frame(b"C", f"REG {my_number}".encode("utf-8"))

# request call
send_frame(b"C", f"CALL {target_number}".encode("utf-8"))

print("Unencrypted LAN call starting...")

in_call = threading.Event()
stop_flag = threading.Event()

# audio setup
audio = pyaudio.PyAudio()

stream_in = audio.open(format=pyaudio.paInt16,
                       channels=1,
                       rate=22050,
                       input=True,
                       frames_per_buffer=1024)

stream_out = audio.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=22050,
                        output=True,
                        frames_per_buffer=1024)


def sender_loop():
    while not stop_flag.is_set():
        data = stream_in.read(1024, exception_on_overflow=False)
        if in_call.is_set():
            send_frame(b"A", data)


def receiver_loop():
    while not stop_flag.is_set():
        msg_type, payload = recv_frame()
        if msg_type is None:
            break

        if msg_type == b"C":
            text = payload.decode("utf-8", errors="replace")
            if text.startswith("OK CALL"):
                in_call.set()
                print(text)
            elif text.startswith("INCOMING "):
                # auto-accept for LAN demo
                caller = text.split(" ", 1)[1]
                send_frame(b"C", f"ACCEPT {caller}".encode("utf-8"))
                in_call.set()
                print(f"Auto-accepted call from {caller}")
            elif text.startswith("ACCEPTED "):
                in_call.set()
                print(text)
            elif text.startswith("ERROR "):
                print(text)
            elif text.startswith("HANGUP "):
                print(text)
                in_call.clear()
        elif msg_type == b"A":
            stream_out.write(payload)

    stop_flag.set()


t1 = threading.Thread(target=sender_loop, daemon=True)
t2 = threading.Thread(target=receiver_loop, daemon=True)

try:
    t1.start()
    t2.start()
    t2.join()
finally:
    stop_flag.set()
    try:
        sock.close()
    except Exception:
        pass
