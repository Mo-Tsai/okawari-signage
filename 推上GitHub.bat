@echo off
chcp 65001 >nul
cd /d "%~dp0"
title OKAWARI 門頭屏 · 推上 GitHub
setlocal

echo.
echo ============================================================
echo   OKAWARI 門頭屏 · 推上 GitHub
echo ============================================================
echo.

where git >nul 2>nul || (echo   找不到 git。先裝：winget install Git.Git & echo. & pause & exit /b 1)
where gh  >nul 2>nul || (echo   找不到 gh。先裝：winget install GitHub.cli & echo. & pause & exit /b 1)

gh auth status >nul 2>nul
if errorlevel 1 (
  echo   還沒登入 GitHub。跑一次 gh auth login，選 HTTPS、用瀏覽器登入。
  echo.
  pause
  exit /b 1
)

if exist ".git" goto push

REM ---------------------------------------------------------- 第一次
echo   第一次執行，建立 repo。
echo.
echo   repo 會設成 public —— GitHub Pages 免費方案只有 public 能發佈網頁。
echo   卡的密碼和門店資料已經被 .gitignore 擋在外面了，不會上傳。
echo.
set "REPO="
set /p REPO=  repo 名字（直接按 Enter 用 okawari-signage）：
if "%REPO%"=="" set "REPO=okawari-signage"

git init -b main || goto fail
git add -A || goto fail
git -c user.useConfigOnly=false commit -m "OKAWARI 門頭屏：後台與控制台介面" || goto fail

echo.
echo   建立 GitHub repo 並推上去…
gh repo create "%REPO%" --public --source=. --push || goto fail

echo.
echo   打開 GitHub Pages（main 分支的 /docs 資料夾）…
gh api -X POST "repos/{owner}/%REPO%/pages" -f "source[branch]=main" -f "source[path]=/docs" >nul 2>nul
if errorlevel 1 echo   （Pages 可能已經開過了，或要手動去 Settings ^> Pages 設成 main /docs）

for /f "delims=" %%A in ('gh api user --jq .login') do set "OWNER=%%A"
echo.
echo ============================================================
echo   好了。網址（第一次要等一兩分鐘才會生效）：
echo.
echo       https://%OWNER%.github.io/%REPO%/
echo.
echo   在那個頁面按右上角「連線設定」，填後台的網址。
echo   同一台電腦的話填 http://localhost:8080
echo ============================================================
echo.
pause
exit /b 0

REM ---------------------------------------------------------- 之後
:push
echo   推送更新…
echo.
git add -A
git diff --cached --quiet && (echo   沒有東西要推，檔案跟上次一樣。& echo. & pause & exit /b 0)

set "MSG="
set /p MSG=  這次改了什麼（直接按 Enter 用「更新」）：
if "%MSG%"=="" set "MSG=更新"

git -c user.useConfigOnly=false commit -m "%MSG%" || goto fail
git push || goto fail

echo.
echo   推上去了。GitHub Pages 大約一分鐘後更新。
echo.
pause
exit /b 0

:fail
echo.
echo   出錯了，上面那段訊息是原因。
echo.
pause
exit /b 1
