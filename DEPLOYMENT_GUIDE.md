# מדריך פריסה והתקנה מלא לשרת הישיבה (Deployment Guide)

מדריך זה מפרט צעד-אחר-צעד כיצד להעביר ולהתקין את המערכת על המחשב הקבוע בישיבה (Ubuntu Server או Windows PC).

---

## 📦 שלב 1: הכנת הקבצים להעברה למחשב היעד

לפני שמעתיקים את התיקייה בדיסק און קי (DOK) או ברשת:

1. **מה להעתיק / לשבט:** שכפל את המאגר באמצעות `git clone` או העתק את תיקיית הפרויקט המלאה.
2. **ממה להימנע (אין צורך להעתיק ידנית):**
   - תיקיית `venv` (תיבנה מחדש במחשב היעד).
   - תיקיות `__pycache__` וקבצי הורדה זמניים.
   - קבצי שמע מתוך `data/incoming/` או `data/sorted/`.

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

## 🌐 שלב 4: חיבור לשרת הקבצים של הישיבה (Windows Server SMB)

כדי לחבר את שרת ההקלטות לשרת ה-Windows הראשי (`\\mdserver\שיעורי שמע\שיעורים למיון`):

1. הרץ את סקריפט החיבור האוטומטי:
   ```bash
   sudo ./setup_smb_mount.sh
   ```
2. הסקריפט יבקש ממך:
   * שם משתמש וסיסמה של משתמש ה-Windows הייעודי לשרת.
   * סיסמת מנהל עבור ממשק ה-Web (ברירת מחדל: `1234`).
3. הסקריפט יגדיר עגינה קבועה ב-`/etc/fstab`, ייצור את תיקיית `שיעורים למיון` בשרת, וישמור את ההגדרות ב-`.env`.

---

## 💻 שלב 5: התקנת תפריט לחיצה ימנית על מחשבי הישיבה (Client Tools)

כדי לאפשר לתלמידים להשאיר הערה ישירות מסייר הקבצים של Windows:

1. העתק את התיקייה `client_tools` על גבי דיסק-און-קי.
2. הכנס את ה-DOK לכל מחשב בישיבה והרץ בלחיצה כפולה את **`install.bat`** (או לחץ פעמיים על `install_context_menu.reg`).
3. מעכשיו, בלחיצה ימנית על כל קובץ שמע (`.mp3`, `.wav`, `.m4a`) יופיע: **"📝 השאר הערה לאחראי שיעורים"** שיפתח את הדפדפן להזנת הערה.

---

## 🧪 שלב 6: בדיקת תקינות המערכת לאחר ההתקנה (Verification)

1. **הפעלת המערכת המלאה (שירות האזנה + ממשק Web):**
   ```bash
   python main.py --all
   ```
   * ממשק הניהול של האחראי זמין בכתובת: `http://<כתובת_שרת>:8000/admin` (סיסמה מוגדרת ב-`.env`).
   * ממשק התלמידים זמין בכתובת: `http://<כתובת_שרת>:8000/student`.

2. **בדיקת שאיבת מקלטים (USB Ingestion):**
   - חבר מקלט שמע / DOK עם הקלטת ניסיון לשקע ה-USB.
   - ודא שהקובץ הועבר ל-`incoming/`, אומת ונמחק מהמקלט מיד, עובד ונשלח ישירות אל `\\mdserver\שיעורי שמע\שיעורים למיון`.

3. **הרצת מבחן 50 השיעורים וניתוח ביצועים (Benchmark):**
   - לאחר עיבוד קבוצת שיעורים, הרץ את כלי הניתוח:
     ```bash
     python analyze_benchmark.py
     ```
   - להפקת דוח Markdown מפורט לקובץ:
     ```bash
     python analyze_benchmark.py --export benchmark_report.md
     ```

---

## 🛠️ פקודות ניהול ותחזוקה שימושיות

| פעולה | פקודה ב-Ubuntu | פקודה ב-Windows |
| :--- | :--- | :--- |
| **משיכת עדכונים מ-GitHub** | `git pull origin feature/web-management` | `git pull origin feature/web-management` |
| **הפעלת מערכת מלאה (Watcher + Web)** | `python main.py --all` | `python main.py --all` |
| **הפעלת שרת Web בלבד** | `python main.py --web` | `python main.py --web` |
| **שינוי סיסמת מנהל ל-Web** | `python set_admin_password.py` | `python set_admin_password.py` |
| **חיבור/עגינת שרת ה-Windows** | `sudo ./setup_smb_mount.sh` | מובנה בווינדוס |
| **בדיקת סטטוס שירות systemd** | `sudo systemctl status recorder.service` | `tasklist \| findstr python` |
| **צפייה בלוגים חיים** | `journalctl -u recorder.service -f` | צפייה בחלון ה-CMD |
| **ניתוח דוח ביצועים ודיוק** | `python analyze_benchmark.py` | `python analyze_benchmark.py` |
| **איפוס נתונים לבדיקות** | `python reset_data.py` | `python reset_data.py` |
| **יצירת נתוני הדמיה לבדיקות** | `python populate_mock_data.py` | `python populate_mock_data.py` |

