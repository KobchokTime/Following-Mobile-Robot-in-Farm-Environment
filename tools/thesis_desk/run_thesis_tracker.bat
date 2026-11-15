@echo off
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 app.py
    goto :done
)
where python >nul 2>nul
if not errorlevel 1 (
    python app.py
    goto :done
)
echo Python 3 was not found. Install Python with Tkinter, then run this file again.
pause
:done
