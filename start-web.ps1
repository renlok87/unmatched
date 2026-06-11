#!/usr/bin/env pwsh
# Запуск opencode web из текущей директории

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

opencode web
