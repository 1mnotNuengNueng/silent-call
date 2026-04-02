import socket
import threading

HOST = "0.0.0.0"
PORT = 5000

clients = {}
lock = threading.Lock()


def handle(conn, addr):
    try:
        # data: phone|listen_port|target
        data = conn.recv(1024).decode(errors="replace")
        phone, listen_port, target = data.split("|")
        listen_port = int(listen_port)

        with lock:
            clients[phone] = (addr[0], listen_port)

        print(f"{phone} registered at {addr[0]}:{listen_port}")

        with lock:
            peer = clients.get(target)

        if peer:
            ip, port = peer
            conn.send(f"PEER|{ip}|{port}".encode())
        else:
            conn.send(b"OFFLINE")

    except Exception as e:
        print("Error:", e)
    finally:
        conn.close()


server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen()

print("Signaling server running...")

while True:
    conn, addr = server.accept()
    threading.Thread(target=handle, args=(conn, addr), daemon=True).start()
