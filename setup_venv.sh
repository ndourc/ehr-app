#!/usr/bin/env bash
# =========================================================
#  Sentiment-Aware EHR Predictive Engine — Linux/macOS Setup
# =========================================================
set -e

VENV_DIR="venv"

echo "[1/5] Creating virtual environment in ./$VENV_DIR ..."
python3 -m venv "$VENV_DIR"

echo "[2/5] Activating virtual environment ..."
source "$VENV_DIR/bin/activate"

echo "[3/5] Upgrading pip ..."
pip install --upgrade pip

echo "[4/5] Installing dependencies ..."
pip install -r requirements.txt

echo "[5/5] Downloading spaCy language model ..."
python -m spacy download en_core_web_sm || {
    echo "WARNING: spaCy model download failed. Run manually:"
    echo "  source $VENV_DIR/bin/activate && python -m spacy download en_core_web_sm"
}

echo ""
echo "========================================================="
echo " Setup complete!"
echo ""
echo " Quick-start:"
echo ""
echo " 1. Copy .env.example to .env and set DATABASE_URL:"
echo "    cp .env.example .env"
echo ""
echo " 2. Train the model (synthetic data):"
echo "    python -m training.train"
echo ""
echo " 3. Start the API server:"
echo "    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo " 4. Run tests:"
echo "    pytest tests/ -v"
echo "========================================================="
