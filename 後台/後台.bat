@echo off
chcp 65001 >nul
cd /d "%~dp0"
title OKAWARI 門頭屏 · 後台（手機可連）

where python >nul 2>nul
if %errorlevel%==0 goto runpython
where py >nul 2>nul
if %errorlevel%==0 goto runpy

echo.
echo   找不到 Python。
echo.
pause
exit /b 1

:runpython
python server.py
goto end

:runpy
py server.py

:end
pause
