@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

REM ==================================================
REM Media2Txt Pro Community launcher
REM Supports:
REM   1. Auto / GPU Auto
REM   2. CPU Only
REM   3. Low Resource
REM   4. GPU Check Only
REM
REM Python priority:
REM   1. Project .venv\Scripts\python.exe
REM   2. System python
REM
REM Whisper model priority:
REM   1. Valid pre-set WHISPER_MODEL_DIR
REM   2. Project local models\faster-whisper-large-v3
REM   3. Parent shared ..\models\faster-whisper-large-v3
REM   4. User Documents shared %USERPROFILE%\Documents\Claude\models\faster-whisper-large-v3
REM   5. Legacy Rossi Documents shared path
REM
REM Notes:
REM   - Relative paths are preferred for portability.
REM   - Absolute legacy path is kept only as a fallback for older home-PC setup.
REM ==================================================

set "BASE_DIR=%~dp0"
set "EXIT_CODE=0"

REM Normalize model candidate paths.
for %%I in ("%BASE_DIR%models\faster-whisper-large-v3") do set "PROJECT_WHISPER_MODEL_DIR=%%~fI"
for %%I in ("%BASE_DIR%..\models\faster-whisper-large-v3") do set "PARENT_WHISPER_MODEL_DIR=%%~fI"

if defined USERPROFILE (
    set "USERPROFILE_WHISPER_MODEL_DIR=%USERPROFILE%\Documents\Claude\models\faster-whisper-large-v3"
) else (
    set "USERPROFILE_WHISPER_MODEL_DIR="
)

set "LEGACY_ROSSI_WHISPER_MODEL_DIR=C:\Users\Rossi\Documents\Claude\models\faster-whisper-large-v3"

REM ==================================================
REM Python executable
REM ==================================================

set "PYTHON_EXE="
if exist "%BASE_DIR%.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%BASE_DIR%.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

REM ==================================================
REM Runtime mode menu
REM ==================================================

echo.
echo ======================================
echo Media2Txt Pro Community launcher
echo ======================================
echo 1. Auto / GPU Auto
echo 2. CPU Only
echo 3. Low Resource
echo 4. GPU Check Only
echo ======================================
choice /c 1234 /n /m "Choose mode [1-4]: "
set "MODE=%ERRORLEVEL%"

echo.

set "MEDIA2TXT_OFFLINE=1"
set "WHISPER_DEVICE=auto"
set "MEDIA2TXT_LOW_RESOURCE=0"
set "GPU_CHECK_ONLY=0"

REM Native crash isolation and stable RTX 3060 defaults.
REM GPU/CTranslate2 work runs in a child process so 0xC0000005 cannot close the UI.
set "MEDIA2TXT_TRANSCRIBE_SUBPROCESS=1"
set "MEDIA2TXT_GPU_COMPUTE_TYPE=int8_float16"
set "MEDIA2TXT_CPU_COMPUTE_TYPE=int8"
set "MEDIA2TXT_LONG_VIDEO_MINUTES=15"
set "MEDIA2TXT_VERY_LONG_VIDEO_MINUTES=40"

if "%MODE%"=="1" (
    set "WHISPER_DEVICE=auto"
    set "MEDIA2TXT_LOW_RESOURCE=0"
)

if "%MODE%"=="2" (
    set "WHISPER_DEVICE=cpu"
    set "MEDIA2TXT_LOW_RESOURCE=0"
)

if "%MODE%"=="3" (
    set "WHISPER_DEVICE=auto"
    set "MEDIA2TXT_LOW_RESOURCE=1"
)

if "%MODE%"=="4" (
    set "WHISPER_DEVICE=auto"
    set "MEDIA2TXT_LOW_RESOURCE=0"
    set "GPU_CHECK_ONLY=1"
)

REM ==================================================
REM Ollama summary model routing
REM Stable mode:
REM   zh -> llama3.1
REM   en -> llama3.1
REM
REM qwen2.5:14b may return Ollama HTTP 500 on 12GB VRAM
REM or high context. Keep llama3.1 as default for stable runs.
REM ==================================================

if not defined OLLAMA_MODEL_ZH (
    set "OLLAMA_MODEL_ZH=llama3.1"
)

if not defined OLLAMA_MODEL_EN (
    set "OLLAMA_MODEL_EN=llama3.1"
)

if not defined OLLAMA_URL (
    set "OLLAMA_URL=http://127.0.0.1:11434/api/generate"
)

if not defined OLLAMA_MODEL_ZH_FALLBACKS (
    set "OLLAMA_MODEL_ZH_FALLBACKS=llama3.1,llama3"
)

if not defined OLLAMA_MODEL_EN_FALLBACKS (
    set "OLLAMA_MODEL_EN_FALLBACKS=llama3.1,llama3"
)

REM ==================================================
REM Whisper model path
REM Relative-first priority:
REM   1. Valid WHISPER_MODEL_DIR already set by user
REM   2. Project local models\faster-whisper-large-v3
REM   3. Parent shared ..\models\faster-whisper-large-v3
REM   4. User Documents shared path using %USERPROFILE%
REM   5. Legacy absolute Rossi path
REM
REM This keeps home PC / company PC / copied project folder all runnable.
REM ==================================================

set "USER_WHISPER_MODEL_DIR=%WHISPER_MODEL_DIR%"
set "WHISPER_MODEL_DIR="

if defined USER_WHISPER_MODEL_DIR (
    if exist "%USER_WHISPER_MODEL_DIR%\model.bin" (
        set "WHISPER_MODEL_DIR=%USER_WHISPER_MODEL_DIR%"
    )
)

if not defined WHISPER_MODEL_DIR (
    if exist "%PROJECT_WHISPER_MODEL_DIR%\model.bin" (
        set "WHISPER_MODEL_DIR=%PROJECT_WHISPER_MODEL_DIR%"
    )
)

if not defined WHISPER_MODEL_DIR (
    if exist "%PARENT_WHISPER_MODEL_DIR%\model.bin" (
        set "WHISPER_MODEL_DIR=%PARENT_WHISPER_MODEL_DIR%"
    )
)

if not defined WHISPER_MODEL_DIR (
    if defined USERPROFILE_WHISPER_MODEL_DIR (
        if exist "%USERPROFILE_WHISPER_MODEL_DIR%\model.bin" (
            set "WHISPER_MODEL_DIR=%USERPROFILE_WHISPER_MODEL_DIR%"
        )
    )
)

if not defined WHISPER_MODEL_DIR (
    if exist "%LEGACY_ROSSI_WHISPER_MODEL_DIR%\model.bin" (
        set "WHISPER_MODEL_DIR=%LEGACY_ROSSI_WHISPER_MODEL_DIR%"
    )
)

REM If all candidates fail, keep project local path as the active default.
REM This makes the UI warning point to the recommended portable location.
if not defined WHISPER_MODEL_DIR (
    set "WHISPER_MODEL_DIR=%PROJECT_WHISPER_MODEL_DIR%"
)

REM ==================================================
REM Detect Python site-packages safely
REM Avoid fragile inline command quoting such as:
REM   'python" -c "import' is not recognized
REM ==================================================

set "SITEPKG="
set "SITEPKG_PROBE=%BASE_DIR%.media2txt_sitepkg_probe.py"

REM Use sysconfig first because it returns the active interpreter site-packages
REM path for both system Python and .venv.  The FOR /F command intentionally wraps
REM cmd /d /s /c with an extra quote pair so full Python paths with spaces are safe.
> "%SITEPKG_PROBE%" echo import sysconfig, site
>>"%SITEPKG_PROBE%" echo paths = []
>>"%SITEPKG_PROBE%" echo purelib = sysconfig.get_paths().get('purelib', '')
>>"%SITEPKG_PROBE%" echo platlib = sysconfig.get_paths().get('platlib', '')
>>"%SITEPKG_PROBE%" echo if purelib: paths.append(purelib)
>>"%SITEPKG_PROBE%" echo if platlib and platlib not in paths: paths.append(platlib)
>>"%SITEPKG_PROBE%" echo for p in site.getsitepackages():
>>"%SITEPKG_PROBE%" echo     if p not in paths: paths.append(p)
>>"%SITEPKG_PROBE%" echo print(paths[0] if paths else '')

for /f "usebackq delims=" %%i in (`cmd /d /s /c ""%PYTHON_EXE%" "%SITEPKG_PROBE%"" 2^>nul`) do (
    set "SITEPKG=%%i"
)

del "%SITEPKG_PROBE%" >nul 2>nul

REM Fallback for known Python 3.12 path if SITEPKG detection fails.
if not defined SITEPKG (
    if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python312\Lib\site-packages" (
        set "SITEPKG=%USERPROFILE%\AppData\Local\Programs\Python\Python312\Lib\site-packages"
    )
)

REM Legacy fallback for older Rossi machine.
if not defined SITEPKG (
    if exist "C:\Users\Rossi\AppData\Local\Programs\Python\Python312\Lib\site-packages" (
        set "SITEPKG=C:\Users\Rossi\AppData\Local\Programs\Python\Python312\Lib\site-packages"
    )
)

REM ==================================================
REM Append NVIDIA DLL paths from Python-installed nvidia packages
REM ==================================================

if defined SITEPKG (
    if exist "%SITEPKG%\nvidia\cublas\bin" (
        set "PATH=%SITEPKG%\nvidia\cublas\bin;%PATH%"
    )
    if exist "%SITEPKG%\nvidia\cudnn\bin" (
        set "PATH=%SITEPKG%\nvidia\cudnn\bin;%PATH%"
    )
    if exist "%SITEPKG%\nvidia\cuda_runtime\bin" (
        set "PATH=%SITEPKG%\nvidia\cuda_runtime\bin;%PATH%"
    )
    if exist "%SITEPKG%\nvidia\cuda_nvrtc\bin" (
        set "PATH=%SITEPKG%\nvidia\cuda_nvrtc\bin;%PATH%"
    )
)

REM ==================================================
REM Detect and append ffmpeg path
REM ==================================================
REM Priority:
REM   1. Valid pre-set FFMPEG_DIR or FFMPEG_PATH
REM   2. Project local tools\ffmpeg\x64 or tools\ffmpeg\bin
REM   3. Parent shared ..\tools\ffmpeg\x64 or ..\tools\ffmpeg\bin
REM   4. JDownloader bundled ffmpeg under %%LOCALAPPDATA%%
REM
REM The JDownloader path contains spaces:
REM   %%LOCALAPPDATA%%\JDownloader 2.0\tools\Windows\ffmpeg\x64
REM so always keep it inside set "VAR=value" quotes.

set "USER_FFMPEG_DIR="
set "USER_FFMPEG_PATH="
set "PROJECT_FFMPEG_DIR="
set "PROJECT_FFMPEG_BIN_DIR="
set "PARENT_FFMPEG_DIR="
set "PARENT_FFMPEG_BIN_DIR="
set "JDOWNLOADER_FFMPEG_DIR="
set "LEGACY_ELUNE_JDOWNLOADER_FFMPEG_DIR="
set "ACTIVE_FFMPEG_DIR="

if defined FFMPEG_DIR (
    if exist "%FFMPEG_DIR%\ffmpeg.exe" (
        for %%I in ("%FFMPEG_DIR%") do set "USER_FFMPEG_DIR=%%~fI"
    )
)

if defined FFMPEG_PATH (
    if exist "%FFMPEG_PATH%" (
        for %%I in ("%FFMPEG_PATH%") do (
            set "USER_FFMPEG_PATH=%%~fI"
            set "USER_FFMPEG_DIR=%%~dpI"
        )
    )
)

for %%I in ("%BASE_DIR%tools\ffmpeg\x64") do set "PROJECT_FFMPEG_DIR=%%~fI"
for %%I in ("%BASE_DIR%tools\ffmpeg\bin") do set "PROJECT_FFMPEG_BIN_DIR=%%~fI"
for %%I in ("%BASE_DIR%..\tools\ffmpeg\x64") do set "PARENT_FFMPEG_DIR=%%~fI"
for %%I in ("%BASE_DIR%..\tools\ffmpeg\bin") do set "PARENT_FFMPEG_BIN_DIR=%%~fI"

if defined LOCALAPPDATA (
    set "JDOWNLOADER_FFMPEG_DIR=%LOCALAPPDATA%\JDownloader 2.0\tools\Windows\ffmpeg\x64"
)
set "LEGACY_ELUNE_JDOWNLOADER_FFMPEG_DIR=C:\Users\elune\AppData\Local\JDownloader 2.0\tools\Windows\ffmpeg\x64"

if not defined ACTIVE_FFMPEG_DIR (
    if defined USER_FFMPEG_DIR (
        if exist "%USER_FFMPEG_DIR%\ffmpeg.exe" (
            set "ACTIVE_FFMPEG_DIR=%USER_FFMPEG_DIR%"
        )
    )
)

if not defined ACTIVE_FFMPEG_DIR (
    if exist "%PROJECT_FFMPEG_DIR%\ffmpeg.exe" (
        set "ACTIVE_FFMPEG_DIR=%PROJECT_FFMPEG_DIR%"
    )
)

if not defined ACTIVE_FFMPEG_DIR (
    if exist "%PROJECT_FFMPEG_BIN_DIR%\ffmpeg.exe" (
        set "ACTIVE_FFMPEG_DIR=%PROJECT_FFMPEG_BIN_DIR%"
    )
)

if not defined ACTIVE_FFMPEG_DIR (
    if exist "%PARENT_FFMPEG_DIR%\ffmpeg.exe" (
        set "ACTIVE_FFMPEG_DIR=%PARENT_FFMPEG_DIR%"
    )
)

if not defined ACTIVE_FFMPEG_DIR (
    if exist "%PARENT_FFMPEG_BIN_DIR%\ffmpeg.exe" (
        set "ACTIVE_FFMPEG_DIR=%PARENT_FFMPEG_BIN_DIR%"
    )
)

if not defined ACTIVE_FFMPEG_DIR (
    if defined JDOWNLOADER_FFMPEG_DIR (
        if exist "%JDOWNLOADER_FFMPEG_DIR%\ffmpeg.exe" (
            set "ACTIVE_FFMPEG_DIR=%JDOWNLOADER_FFMPEG_DIR%"
        )
    )
)

if not defined ACTIVE_FFMPEG_DIR (
    if exist "%LEGACY_ELUNE_JDOWNLOADER_FFMPEG_DIR%\ffmpeg.exe" (
        set "ACTIVE_FFMPEG_DIR=%LEGACY_ELUNE_JDOWNLOADER_FFMPEG_DIR%"
    )
)

if defined ACTIVE_FFMPEG_DIR (
    set "FFMPEG_DIR=%ACTIVE_FFMPEG_DIR%"
    set "FFMPEG_BINARY=%ACTIVE_FFMPEG_DIR%\ffmpeg.exe"
    set "FFPROBE_BINARY=%ACTIVE_FFMPEG_DIR%\ffprobe.exe"
    set "PATH=%ACTIVE_FFMPEG_DIR%;%PATH%"
)

REM ==================================================
REM Print environment
REM ==================================================

echo ======================================
echo Media2Txt Pro Community runtime
echo PYTHON_EXE=%PYTHON_EXE%
echo SITEPKG=%SITEPKG%
echo ACTIVE_FFMPEG_DIR=%ACTIVE_FFMPEG_DIR%
echo FFMPEG_BINARY=%FFMPEG_BINARY%
echo USER_WHISPER_MODEL_DIR=%USER_WHISPER_MODEL_DIR%
echo PROJECT_WHISPER_MODEL_DIR=%PROJECT_WHISPER_MODEL_DIR%
echo PARENT_WHISPER_MODEL_DIR=%PARENT_WHISPER_MODEL_DIR%
echo USERPROFILE_WHISPER_MODEL_DIR=%USERPROFILE_WHISPER_MODEL_DIR%
echo LEGACY_ROSSI_WHISPER_MODEL_DIR=%LEGACY_ROSSI_WHISPER_MODEL_DIR%
echo WHISPER_MODEL_DIR=%WHISPER_MODEL_DIR%
echo MEDIA2TXT_OFFLINE=%MEDIA2TXT_OFFLINE%
echo WHISPER_DEVICE=%WHISPER_DEVICE%
echo MEDIA2TXT_LOW_RESOURCE=%MEDIA2TXT_LOW_RESOURCE%
echo OLLAMA_MODEL_ZH=%OLLAMA_MODEL_ZH%
echo OLLAMA_MODEL_EN=%OLLAMA_MODEL_EN%
echo OLLAMA_URL=%OLLAMA_URL%
echo GPU_CHECK_ONLY=%GPU_CHECK_ONLY%
echo MEDIA2TXT_TRANSCRIBE_SUBPROCESS=%MEDIA2TXT_TRANSCRIBE_SUBPROCESS%
echo MEDIA2TXT_GPU_COMPUTE_TYPE=%MEDIA2TXT_GPU_COMPUTE_TYPE%
echo MEDIA2TXT_LONG_VIDEO_MINUTES=%MEDIA2TXT_LONG_VIDEO_MINUTES%
echo MEDIA2TXT_VERY_LONG_VIDEO_MINUTES=%MEDIA2TXT_VERY_LONG_VIDEO_MINUTES%
echo ======================================
echo.

"%PYTHON_EXE%" --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python is not available.
    echo PYTHON_EXE=%PYTHON_EXE%
    echo.
    echo Please install Python 3.10 or newer, or create .venv first.
    echo.
    pause
    exit /b 1
)

if not exist "%WHISPER_MODEL_DIR%\model.bin" (
    echo [WARN] Local Whisper model not found:
    echo %WHISPER_MODEL_DIR%
    echo.
    echo Checked:
    echo 1. Valid pre-set WHISPER_MODEL_DIR: %USER_WHISPER_MODEL_DIR%
    echo 2. Project local: %PROJECT_WHISPER_MODEL_DIR%
    echo 3. Parent shared: %PARENT_WHISPER_MODEL_DIR%
    echo 4. User Documents shared: %USERPROFILE_WHISPER_MODEL_DIR%
    echo 5. Legacy Rossi shared: %LEGACY_ROSSI_WHISPER_MODEL_DIR%
    echo.
    echo MEDIA2TXT_OFFLINE=%MEDIA2TXT_OFFLINE%
    echo Tasks that require Whisper transcription will fail until a local model is available.
    echo Tasks with usable subtitles may still work.
    echo.
) else (
    echo [OK] Whisper model found:
    echo %WHISPER_MODEL_DIR%
    echo.
)

if defined ACTIVE_FFMPEG_DIR (
    echo [OK] ffmpeg found:
    echo %ACTIVE_FFMPEG_DIR%\ffmpeg.exe
    echo.
) else (
    echo [WARN] ffmpeg.exe was not found in launcher search paths.
    echo Checked:
    echo 1. Pre-set FFMPEG_DIR / FFMPEG_PATH
    echo 2. Project local: %PROJECT_FFMPEG_DIR%
    echo 3. Project local: %PROJECT_FFMPEG_BIN_DIR%
    echo 4. Parent shared: %PARENT_FFMPEG_DIR%
    echo 5. Parent shared: %PARENT_FFMPEG_BIN_DIR%
    echo 6. JDownloader: %JDOWNLOADER_FFMPEG_DIR%
    echo 7. Legacy elune JDownloader: %LEGACY_ELUNE_JDOWNLOADER_FFMPEG_DIR%
    echo.
)

if "%GPU_CHECK_ONLY%"=="1" (
    echo [GPU CHECK ONLY]
    echo.
    "%PYTHON_EXE%" -c "import sys, os; print('python=', sys.executable); print('sitepkg=', os.environ.get('SITEPKG','')); print('WHISPER_MODEL_DIR=', os.environ.get('WHISPER_MODEL_DIR','')); import av; print('av=OK'); import ctranslate2; print('ctranslate2=', ctranslate2.__version__); from pipeline.ffmpeg_utils import get_ffmpeg_info; print('ffmpeg=', get_ffmpeg_info()); from pipeline.transcriber import get_transcriber_runtime_info, can_use_cuda_for_transcribe; print('runtime=', get_transcriber_runtime_info()); print('cuda=', can_use_cuda_for_transcribe())"
    set "EXIT_CODE=%ERRORLEVEL%"
    echo.
    call :cleanup_runtime_dirs
    echo.
    echo GPU check finished. EXIT_CODE=%EXIT_CODE%
    pause
    exit /b %EXIT_CODE%
)

echo Starting app...
echo.
"%PYTHON_EXE%" main.py
set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo App closed. EXIT_CODE=%EXIT_CODE%
call :cleanup_runtime_dirs

echo.
pause
exit /b %EXIT_CODE%

:cleanup_runtime_dirs
echo Cleaning runtime temp folders...
for %%D in ("%BASE_DIR%data\tmp" "%BASE_DIR%data\cache" "%BASE_DIR%data\downloads" "%BASE_DIR%data\temp") do (
    if exist "%%~D" (
        rd /s /q "%%~D" >nul 2>nul
    )
    mkdir "%%~D" >nul 2>nul
)
echo Cleanup done. Preserved: knowledge, knowledge\_meta, logs, models.
exit /b 0
