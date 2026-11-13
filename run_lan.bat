@echo off
cd /d %~dp0
if not exist .venv\Scripts\python.exe (
  echo Please run setup_cpu.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\activate
set OMP_NUM_THREADS=4
set MKL_NUM_THREADS=4
set DOTS_DEVICE=cpu
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
pause
