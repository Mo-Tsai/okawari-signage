@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 灰度控制卡 現場測試工具

where python >nul 2>nul
if %errorlevel%==0 goto runpython
where py >nul 2>nul
if %errorlevel%==0 goto runpy

echo.
echo   找不到 Python。
echo   改用旁邊「官方測試工具」資料夾裡的 SDKTest.exe，那個不用裝東西。
echo.
pause
exit /b 1

:runpython
python hd_test.py
goto end

:runpy
py hd_test.py

:end
pause
