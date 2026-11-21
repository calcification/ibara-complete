@echo off
rem Drag "Ibara (Japan).iso" onto this file (optionally together with your ibarablk.zip for the Black Label RANK bar
rem artwork). Writes "Ibara KURO.iso" next to the ISO.
if "%~1"=="" (echo Drag your "Ibara (Japan).iso" onto this file.& pause & exit /b 1)
set ISO=%~1
set ROM=
if /i "%~x1"==".zip" (set ROM=%~1& set ISO=%~2)
if /i "%~x2"==".zip" set ROM=%~2
for %%F in ("%ISO%") do set OUT=%%~dpFIbara KURO.iso
if defined ROM (
  py -3 "%~dp0apply_kuro_patch.py" "%ISO%" "%OUT%" --bl-rom "%ROM%" || python "%~dp0apply_kuro_patch.py" "%ISO%" "%OUT%" --bl-rom "%ROM%"
) else (
  py -3 "%~dp0apply_kuro_patch.py" "%ISO%" "%OUT%" || python "%~dp0apply_kuro_patch.py" "%ISO%" "%OUT%"
)
pause
