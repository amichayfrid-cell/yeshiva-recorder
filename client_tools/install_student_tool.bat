@echo off
:: מונע בעיות של הפעלת קובץ רשת ב-Windows
copy /y "%~dp0install_menu_clean.reg" "%TEMP%\install_menu.reg" >nul
start "" "%TEMP%\install_menu.reg"
