@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0stop-project.ps1" %*
