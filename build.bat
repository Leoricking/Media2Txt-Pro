@echo off
chcp 65001 >nul
setlocal

echo ========================================
echo        Build Media2Txt Pro
echo ========================================

REM 建議先啟用虛擬環境後再執行本檔
REM 例如：
REM .venv\Scripts\activate

python --version
if errorlevel 1 (
    echo [ERROR] Python not found.
    pause
    exit /b 1
)

echo.
echo [1/4] Installing requirements...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install requirements.
    pause
    exit /b 1
)

echo.
echo [2/4] Installing PyInstaller...
python -m pip install pyinstaller
if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller.
    pause
    exit /b 1
)

echo.
echo [3/4] Cleaning old build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo [4/4] Building EXE...
if exist Media2Txt.spec (
    pyinstaller Media2Txt.spec
) else (
    pyinstaller --noconfirm --clean --windowed --name Media2Txt main.py
)

if errorlevel 1 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build completed successfully.
echo Output: dist\Media2Txt\
echo ========================================
pause
