@echo off
REM =========================================================
REM  Sentiment-Aware EHR Predictive Engine — Windows Setup
REM =========================================================

SET VENV_DIR=venv

echo [1/5] Creating virtual environment in .\%VENV_DIR% ...
python -m venv %VENV_DIR%
IF ERRORLEVEL 1 (
    echo ERROR: Could not create virtual environment. Ensure Python 3.10+ is installed.
    exit /b 1
)

echo [2/5] Activating virtual environment ...
CALL %VENV_DIR%\Scripts\activate.bat

echo [3/5] Upgrading pip ...
python -m pip install --upgrade pip

echo [4/5] Installing dependencies ...
pip install -r requirements.txt
IF ERRORLEVEL 1 (
    echo ERROR: pip install failed.
    exit /b 1
)

echo [5/5] Downloading spaCy language model ...
python -m spacy download en_core_web_sm
IF ERRORLEVEL 1 (
    echo WARNING: spaCy model download failed. Run manually:
    echo   %VENV_DIR%\Scripts\activate ^& python -m spacy download en_core_web_sm
)

echo.
echo =========================================================
echo  Setup complete!
echo.
echo  Quick-start:
echo.
echo  1. Copy .env.example to .env and populate DATABASE_URL:
echo     copy .env.example .env
echo.
echo  2. Train the model (synthetic data):
echo     python -m training.train
echo.
echo  3. Start the API server:
echo     uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
echo.
echo  4. Run tests:
echo     pytest tests/ -v
echo =========================================================
