import socket
import threading
import wave
import atexit
import time

HOST = "0.0.0.0"
PORT_A = 6001
PORT_B = 6002

BUFFER = 8192

wav_ab = wave.open("A_to_B.wav", "wb")
wav_ba = wave.open("B_to_A.wav", "wb")

for w in (wav_ab, wav_ba):
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(22050)


def close_wav():
    wav_ab.close()
    wav_ba.close()


atexit.register(close_wav)


def relay(src, dst, wav, label):
    try:
        while True:
            data = src.recv(BUFFER)
            if not data:
                break

            wav.writeframesraw(data)
            dst.sendall(data)
    except (ConnectionResetError, OSError):
        pass
    finally:
        try:
            src.close()
        except Exception:
            pass
        try:
            dst.close()
        except Exception:
            pass
        print(f"[MITM] {label} closed")


def wait_client(port, name):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, port))
    s.listen(1)

    print(f"[MITM] Waiting {name} on port {port}...")
    conn, addr = s.accept()
    print(f"[MITM] {name} connected:", addr)

    return conn


def main():
    A = wait_client(PORT_A, "A")
    B = wait_client(PORT_B, "B")

    threading.Thread(target=relay, args=(A, B, wav_ab, "A->B"), daemon=True).start()
    threading.Thread(target=relay, args=(B, A, wav_ba, "B->A"), daemon=True).start()

    while True:
        time.sleep(0.5)


if __name__ == "__main__":
    main()
