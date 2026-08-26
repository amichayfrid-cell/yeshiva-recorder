# מדריך פריסה והתקנה מלא לשרת הישיבה (Deployment Guide)

מדריך זה מפרט צעד-אחר-צעד כיצד להעביר ולהתקין את המערכת על המחשב הקבוע בישיבה (Ubuntu Server או Windows PC).

---

## 📦 שלב 1: הכנת הקבצים להעברה למחשב היעד

לפני שמעתיקים את התיקייה בדיסק און קי (DOK) או ברשת:

1. **מה להעתיק:** העתק את תיקיית הפרויקט `yeshiva-recorder-main`.
2. **ממה להימנע (אין צורך להעתיק):**
   - תיקיית `venv` (תיבנה מחדש במחשב היעד).
   - תיקיות `__pycache__` ו-`.git`.
   - קבצי שמע זמניים מתוך `data/incoming/` או `data/sorted/`.

---

## 🐧 שלב 2: התקנה על Ubuntu Server (מומלץ)

אם מחשב היעד מריץ **Ubuntu Server / Linux**:

### א. התקנה אוטומטית (בפקודה אחת)
1. העתק את התיקייה לשרת (למשל לנתיב `/opt/yeshiva-recorder` או לתיקיית הבית).
2. פתח טרמינל בתיקיית הפרויקט והרץ:
```bash
chmod +x install.sh
sudo ./install.sh
```

**מה הסקריפט עושה אוטומטית?**
- מתקין `ffmpeg`, `python3`, `python3-venv`, `git`, `curl`.
- יוצר סביבה וירטואלית `venv` ומתקין את תלויות ה-Python.
- מתקין את `Ollama` ומוריד את מודל השפה `gemma4:e2b`.
- מגדיר ומפעיל שירות רקע אוטומטי (`recorder.service`) שירוץ תמיד ברקע ויעלה עם הדלקת המחשב.

---

### ב. התקנה ידנית (חלופי)
אם תרצה לבצע את השלבים ידנית:

1. **התקנת חבילות מערכת:**
   ```bash
   sudo apt update && sudo apt install -y ffmpeg python3-pip python3-venv git curl
   ```

2. **התקנת Ollama והורדת מודל:**
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ollama pull gemma4:e2b
   ```

3. **הגדרת סביבת Python:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **הפעלת השירות ברקע (`systemd`):**
   ```bash
   sudo cp recorder.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable recorder.service
   sudo systemctl start recorder.service
   ```

---

## 🪟 שלב 3: התקנה על Windows PC

אם מחשב היעד מריץ **Windows**:

1. **דרישות מוקדמות:**
   - ודא מותקן **Python 3.10 ומעלה** (סמן ב-V את "Add Python to PATH" בעת ההתקנה).
   - הורד והתקן את **Ollama for Windows** מ- [https://ollama.com](https://ollama.com).

2. **הרצת התקנה אוטומטית:**
   - כנס לתיקיית הפרויקט והרצ כמנהל (Run as Administrator) את הקובץ:
     `setup_windows.bat`
   - הסקריפט יתקין את תלויות ה-Python, יוריד את המודל `gemma4:e2b` ויבדוק את תקינות `ffmpeg`.

3. **הרצת המערכת ב-Windows:**
   - הפעלה ידנית מתוך PowerShell / CMD:
     ```cmd
     venv\Scripts\activate
     python main.py
     ```
   - להפעלה אוטומטית ברקע בעליית המחשב: ניתן להוסיף קיצור דרך ל-`setup_windows.bat` או ל-`main.py` לתיקיית ה-Startup (`shell:startup`), או להגדיר ב-Task Scheduler.

---

## 🧪 שלב 4: בדיקת תקינות המערכת לאחר ההתקנה (Verification)

1. **בדיקת מודלים:**
   - הרץ סריקה ראשונית:
     ```bash
     python main.py --scan
     ```
   - ודא שאין שגיאות טעינה של Whisper או התחברות ל-Ollama.

2. **בדיקת שאיבת מקלטים (USB Ingestion):**
   - חבר מקלט שמע / דיסק און קי עם הקלטת ניסיון לשקע ה-USB.
   - הרץ את שירות שאיבת ה-USB:
     ```bash
     python test_usb_ingest.py
     ```
   - ודא שהקובץ הועבר ל-`data/incoming/`, מוין ל-`data/sorted/`, ונמחק מהמקלט (אם מוגדר `USB_DELETE_AFTER_INGEST = True`).

---

## 🛠️ פקודות ניהול ותחזוקה שימושיות

| פעולה | פקודה ב-Ubuntu | פקודה ב-Windows |
| :--- | :--- | :--- |
| **בדיקת סטטוס שירות** | `sudo systemctl status recorder.service` | `tasklist \| findstr python` |
| **צפייה בלוגים חיים** | `journalctl -u recorder.service -f` | צפייה בחלון ה-CMD |
| **איפוס נתונים לבדיקות** | `python reset_data.py` | `python reset_data.py` |
| **סריקת שאיבה חד-פעמית** | `python test_usb_ingest.py` | `python test_usb_ingest.py` |
