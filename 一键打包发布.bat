@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   一键打包发布
echo ============================================

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\package_release.py --publish --auto-commit %*
) else (
    python scripts\package_release.py --publish --auto-commit %*
)

if errorlevel 1 (
    echo.
    echo 打包或发布失败，请检查上方日志。
    pause
    exit /b 1
)

echo.
echo 打包发布完成，zip 位于 dist 目录。
timeout /t 5 >nul
