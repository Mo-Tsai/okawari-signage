@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 現場一鍵連線 · OKAWARI 門頭屏

where python >nul 2>nul
if %errorlevel%==0 goto runpython
where py >nul 2>nul
if %errorlevel%==0 goto runpy

echo.
echo   找不到 Python。
echo   改用旁邊「官方測試工具」資料夾裡的 SDKTest.exe。
echo.
pause
exit /b 1

:runpython
python 現場連線.py
goto end

:runpy
py 現場連線.py

:end
