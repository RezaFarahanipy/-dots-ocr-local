@echo off
setlocal
cd /d %~dp0
echo === Dots OCR Local: CPU setup ===
py -3.12 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.12 64-bit was not found. Install Python 3.12 and enable Add Python to PATH.
  pause
  exit /b 1
)
if not exist .venv (
  py -3.12 -m venv .venv
)
call .venv\Scripts\activate
python -m pip install --upgrade pip
echo Installing CPU-only PyTorch...
pip install torch==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cpu
echo Installing web app dependencies...
pip install -r requirements.txt
if not exist vendor\dots.ocr (
  git clone https://github.com/studio-dots-ai/dots.ocr.git vendor\dots.ocr
)
echo Installing Dots OCR source...
pip install -e vendor\dots.ocr --no-deps
pip install transformers==4.56.1 accelerate qwen-vl-utils huggingface_hub modelscope cairosvg
echo.
echo Setup completed. Next:
echo 1. cd vendor\dots.ocr
echo 2. python tools\download_model.py
echo 3. Return to project folder and run run.bat
pause
