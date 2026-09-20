@echo off
rem Juanzong one-click stopper: kills llama servers + Gradio UI
echo [1/2] Stopping Gradio UI (port 7860)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :7860 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
taskkill /f /t /fi "WINDOWTITLE eq Juanzong-Gradio*" >nul 2>&1

echo [2/2] Stopping llama servers (ports 11435 / 11436)...
taskkill /f /im llama-server.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":11435 :11436" ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
taskkill /f /t /fi "WINDOWTITLE eq Juanzong-Llama*" >nul 2>&1

echo.
echo All stopped.
pause
