@echo off
rem Launch the packaged Unmatched client with the user-only environment variant
rem (-EnvLayoutVariant=user): Megaplants Yoshino cherries on Marmoreal and StyleHex rocks on
rem Sarpedon (NoAI Fab packs, local personal use only; decisions ENV-U13/U14). Without this
rem flag the client uses the default variant (Forest pink trees). Extra arguments are passed
rem through, e.g.  Unmatched-Yoshino.cmd -S08Api=http://localhost:3120/graphql
setlocal
set "STAGED=%~dp0..\..\unreal\Unmatched\Saved\StagedBuilds\Windows\Unmatched.exe"
if not exist "%STAGED%" (
  echo Packaged client not found: %STAGED%
  echo Build it first: powershell -File tools\s08\package-client.ps1
  pause
  exit /b 1
)
start "" "%STAGED%" -EnvLayoutVariant=user %*
