@echo off
chcp 65001 >nul
title עדכון שרת שיעורי הישיבה - Yeshiva Recorder Deploy
echo ========================================================
echo   עדכון שרת שיעורי הישיבה (Yeshiva Recorder)
echo ========================================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy.ps1"
echo.
echo ========================================================
pause
