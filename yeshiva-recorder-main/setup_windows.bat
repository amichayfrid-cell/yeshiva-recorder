@echo off
chcp 65001 > NUL
echo ===================================================
echo   התקנת מערכת מיון שיעורי תורה (Windows)
echo ===================================================

echo.
echo [1/3] יוצר סביבה וירטואלית ומתקין ספריות Python...
python -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo [2/3] בודק התקנת Ollama והורדת מודל Gemma 4...
where ollama >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] Ollama לא נמצא! אנא הורד והתקן את Ollama מ- https://ollama.com ולאחר מכן הרץ סקריפט זה שוב.
    pause
    exit /b 1
)
ollama pull gemma4:e2b

echo.
echo [3/3] בודק התקנת FFmpeg...
where ffmpeg >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] אזהרה: FFmpeg לא נמצא ב-PATH.
    echo לחץ מקש כלשהו להתקנה אוטומטית של FFmpeg דרך winget, או התקן מ- https://ffmpeg.org
    pause
    winget install Gyan.FFmpeg
)

echo.
echo ===================================================
echo   ✓ ההתקנה הושלמה!
echo   להרצת המערכת ב-Windows:
echo   call venv\Scripts\activate
echo   python main.py
echo ===================================================
pause
