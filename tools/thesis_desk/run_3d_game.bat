@echo off
cd /d "%~dp0"
set "GODOT=%~dp0.tools\godot\Godot_v4.7.2-stable_win64.exe"
if not exist "%GODOT%" (
  echo Godot portable executable was not found at .tools\godot\
  pause
  exit /b 1
)
"%GODOT%" --path "%~dp0godot_game"
