@echo off
rem 分离式拉起 llama 双模型(供计划任务/手动使用)
cd /d "%~dp0.."
"C:\Users\54780\.workbuddy\binaries\python\envs\default\Scripts\python.exe" scripts\detach_llama.py --no-wait
