import os
import getpass
from pathlib import Path

def set_password():
    print("=" * 60)
    print(" הגדרת סיסמת מנהל לממשק ה-Web (Admin Dashboard)")
    print("=" * 60)
    
    env_file = Path(__file__).resolve().parent / ".env"
    
    pass1 = getpass.getpass("הזן סיסמת מנהל חדשה: ").strip()
    if not pass1:
        print("[!] לא הוזנה סיסמה. הפעולה בוטלה.")
        return
        
    pass2 = getpass.getpass("הזן את הסיסמה שוב לאימות: ").strip()
    if pass1 != pass2:
        print("[X] הסיסמאות אינן תואמות! הפעולה בוטלה.")
        return

    # Read existing env content or create new
    existing_lines = []
    if env_file.exists():
        existing_lines = env_file.read_text(encoding="utf-8").splitlines()

    new_lines = []
    found = False
    for line in existing_lines:
        if line.startswith("ADMIN_PASSWORD="):
            new_lines.append(f"ADMIN_PASSWORD={pass1}")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"ADMIN_PASSWORD={pass1}")

    env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"\n[✓] הסיסמה החדשה נשמרה בהצלחה בקובץ {env_file.name}!")
    print("[✓] הסיסמה תהיה תקפה מיידית בכניסה הבאה לממשק ה-Web.")
    print("=" * 60)

if __name__ == "__main__":
    set_password()
