@echo off
rem Art Tuner (tools\art\ART-TUNER.md): the board without a server + the tuning panel.
rem   Unmatched-ArtTuner.cmd [sarpedon or marmoreal] [extra client arguments]
rem The original maps only (2026-10-04, docs\game-design\decisions\2026-10-04-real-boards-only.md).
rem F10 opens the panel, F1 the keys. "Save" (Ctrl+S) writes the changed values to
rem unreal\Unmatched\Config\ArtBoards\S08ArtTuner.overrides.json (local, not in git); the next start puts them back,
rem and the AI agents write them into the profile with tools\art\art_tuner_fold.py.
rem Personal, local use only.
setlocal
for %%I in ("%~dp0..\..") do set "ROOT=%%~fI"
set "STAGED=%ROOT%\unreal\Unmatched\Saved\StagedBuilds\Windows\Unmatched.exe"
set "SAVE=%ROOT%\unreal\Unmatched\Config\ArtBoards\S08ArtTuner.overrides.json"
set "MAP=%~1"
if "%MAP%"=="" set "MAP=sarpedon"
if /I not "%MAP%"=="sarpedon" if /I not "%MAP%"=="marmoreal" (
  echo Unknown map "%MAP%": use sarpedon or marmoreal.
  pause
  exit /b 1
)
if not exist "%STAGED%" (
  echo Packaged client not found: %STAGED%
  echo Build it first: powershell -File tools\s08\package-client.ps1
  pause
  exit /b 1
)
set "EXTRA="
:collect
shift
if "%~1"=="" goto run
set EXTRA=%EXTRA% %1
goto collect
:run
start "" "%STAGED%" -ArtView=%MAP% -ArtTuner -ArtTunerFile="%SAVE%" -ArtPreview -ArtPreviewDiorama -ArtPreviewHeroesV2 -windowed -ResX=1920 -ResY=1080 %EXTRA%
