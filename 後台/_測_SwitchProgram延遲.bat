@echo off
chcp 65001 >nul
cd /d "%~dp0"
python "_測_SwitchProgram延遲.py" %*
pause
