@echo off
rem Juanzong desktop app launcher: opens standalone window (no console)
rem Path with spaces/Chinese is handled by %~dp0 - keep this file pure ASCII inside.
cd /d "%~dp0"
start "" "C:\Users\54780\.workbuddy\binaries\python\envs\default\Scripts\pythonw.exe" desktop.py
