@echo off
rem Drag "Ibara (Japan).iso" onto this file. Writes "Ibara KURO.iso" next to it.
if "%~1"=="" (echo Drag your "Ibara (Japan).iso" onto this file.& pause & exit /b 1)
py -3 "%~dp0apply_kuro_patch.py" "%~1" "%~dp1Ibara KURO.iso" || python "%~dp0apply_kuro_patch.py" "%~1" "%~dp1Ibara KURO.iso"
pause
