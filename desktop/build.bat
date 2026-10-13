@echo off
cd /d "%~dp0"
py -m venv .venv
if errorlevel 1 goto fail
call .venv\Scripts\python.exe -m pip install --upgrade pip
call .venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto fail
call .venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --onedir --name UsbMirror app.py
if errorlevel 1 goto fail
if not exist dist\UsbMirror\tools mkdir dist\UsbMirror\tools
if exist tools\*.* copy /y tools\*.* dist\UsbMirror\tools\ >nul
echo Built dist\UsbMirror\UsbMirror.exe
echo Ensure adb.exe, both ADB DLLs and ffmpeg.exe are in dist\UsbMirror\tools
pause
exit /b 0
:fail
echo Build failed
pause
