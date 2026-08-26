@echo off
chcp 65001 >nul
echo ======================================================================
echo   ישיבת מדברה כעדן - הפעלת שרת הזרמת שיעורי מו"ר הרב צבי שליט"א
echo ======================================================================
echo.

set WEB_HOST=0.0.0.0
set WEB_PORT=8000
if "%RAV_TZVI_DIR%"=="" (
    set RAV_TZVI_DIR=D:\שיעורי שמע\הרב צבי קוסטינר
)

echo [✓] כתובת האזנה: http://%WEB_HOST%:%WEB_PORT%/rav-tzvi
echo [✓] תיקיית מקור: %RAV_TZVI_DIR%
echo.
echo מפעיל שרת הזרמה מוגן...
python main.py --web

pause
