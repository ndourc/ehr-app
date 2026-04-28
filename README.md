# Sentiment-Aware EHR Predictive Engine

A real-time hybrid machine learning system that predicts psychological **Distress** by fusing unstructured clinical notes with structured behavioural metrics. Built as a decision-support subsystem for Electronic Health Record (EHR) environments.

---

## What the System Can Do

### Prediction
- Accepts a dual-stream payload (free-text clinical note + 16 ordinal behavioural scores) and returns a binary prediction: **Distress** or **Stable**
- Returns a **confidence score** (probability) between 0.0 and 1.0 alongside every prediction
- Operates in real time via a REST API; inference latency is tracked and stored per request

### Natural Language Understanding
- Encodes clinical text using **ClinicalBERT** (`medicalai/ClinicalBERT`), a domain-specific transformer pretrained on clinical corpora
- Preprocessing pipeline handles: template/boilerplate removal, contraction expansion, lowercasing, special-character stripping, negation preservation (`not_<word>`), and spaCy lemmatization
- Supports clinical notes up to 512 tokens

### Structured Feature Analysis
- Ingests 16 ordinal behavioural variables (scale 0–3) across four clinical domains:
  - Psychological State (mood swings, anxiety, depression, emotional stability)
  - Behavioural Patterns (days indoors, social interaction, activity, sleep quality)
  - Coping & Stress (coping struggles, stress level, work engagement, motivation)
  - Cognitive Function & Social Context (concentration, decision difficulty, memory, support system)
- Applies MinMax normalisation before fusion

### Hybrid Fusion & Classification
- Concatenates the 768-d ClinicalBERT CLS embedding with the 16-d normalised structured vector into a 784-d hybrid feature vector
- Classifies using a **Random Forest + SVM ensemble** with class-weighted loss (configurable distress weight, default 3×) to handle clinical class imbalance
- Training applies **SMOTE** oversampling on the training split

### Explainability (XAI)
- Extracts per-word attention weights from all ClinicalBERT layers and heads
- Aggregates sub-word (WordPiece) tokens back to whole words using max-pooling
- Returns the **top-k most influential words** (default k=10) with their normalised importance scores, enabling clinicians to understand what language drove the prediction
- Negation-preserved tokens (e.g. `not_eating`) are surfaced in human-readable form

### API
- `POST /api/v1/predict` — full inference with XAI output
- `GET /api/v1/health` — liveness check; reports pipeline readiness
- `GET /api/v1/records` — paginated, filterable audit log of all past predictions

### Auditability & Storage
- Every prediction is persisted to a database (PostgreSQL / SQLite) including: raw inputs, cleaned text, normalised features, prediction, confidence, token importances, sentiment, token count, and latency
- Structured JSON logging for all inference events and errors

### Training & Evaluation
- Trains end-to-end from either a CSV dataset or **synthetic data** (no real patient data required to get started)
- Evaluation reports: accuracy, distress recall, F1, and ROC-AUC
- **Ablation study** tool compares three variants side-by-side: Structured-Only, NLP-Only, and Hybrid

### Frontend
- React + TypeScript UI (Vite + shadcn/ui) for submitting predictions and viewing results
- Components for prediction output, XAI token highlighting, severity picking, metrics display, and audit log browsing

---

## Current Limitations

- The classifier is trained on **synthetic data** by default; real-world performance depends on fine-tuning with clinical datasets
- ClinicalBERT input is capped at **512 tokens** — longer notes are truncated
- No authentication or authorisation layer on the API endpoints currently
- Explainability is attention-based (not SHAP/LIME); attention weights are a proxy for importance, not a guarantee

---

---

## Architecture Overview

The system is structured as four independent, interconnected layers.

```
┌──────────────────────────────────────────────────────────────────────┐
│  POST /api/v1/predict                                                │
│                                                                      │
│  ┌──────────────────┐     ┌──────────────────────────────────────┐  │
│  │  Layer 1         │     │  JSON Payload                        │  │
│  │  Data Ingestion  │◄────│  patient_id, timestamp,              │  │
│  │  (Pydantic)      │     │  clinical_text + 16 structured vars  │  │
│  └────────┬─────────┘     └──────────────────────────────────────┘  │
│           │                                                          │
│  ┌────────▼─────────┐                                               │
│  │  Layer 2         │  Text pipeline: template removal →            │
│  │  Processing      │  contraction expansion → lowercase →          │
│  │                  │  special-char removal → negation preservation │
│  │                  │  → lemmatization (spaCy)                      │
│  │                  │──────────────────────────────────────────►    │
│  │                  │  Structured pipeline: validate → MinMax norm  │
│  └────────┬─────────┘                                               │
│           │                                                          │
│  ┌────────▼─────────┐                                               │
│  │  Layer 3         │  ClinicalBERT → CLS embedding (768-d)         │
│  │  Model           │  Fusion: concat(embedding, structured) = 784-d│
│  │  (Hybrid Fusion) │  Ensemble: RF + SVM → P(Distress)             │
│  └────────┬─────────┘                                               │
│           │                                                          │
│  ┌────────▼─────────┐                                               │
│  │  Layer 4         │  Prediction + Confidence                      │
│  │  Output &        │  Attention extraction → token importance map  │
│  │  Explainability  │  → PredictResponse (prediction + XAI)         │
│  └──────────────────┘                                               │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Codebase Structure

```
caroe/
├── app/
│   ├── main.py                        # FastAPI application entry point
│   ├── config.py                      # All settings (pydantic-settings)
│   ├── utils/
│   │   └── logging_config.py          # Structured JSON logging
│   ├── layers/
│   │   ├── ingestion/
│   │   │   ├── schemas.py             # Layer 1: Pydantic contracts
│   │   │   └── validator.py           # Layer 1: Extended semantic validation
│   │   ├── processing/
│   │   │   ├── text_processor.py      # Layer 2: 6-step NLP preprocessing
│   │   │   └── structured_processor.py# Layer 2: Feature normalisation
│   │   ├── model/
│   │   │   ├── nlp_engine.py          # Layer 3: ClinicalBERT encoder
│   │   │   ├── fusion_layer.py        # Layer 3: Hybrid vector construction
│   │   │   └── classifier.py          # Layer 3: RF + SVM ensemble
│   │   └── output/
│   │       ├── explainer.py           # Layer 4: Attention → token weights
│   │       └── predictor.py           # Layer 4: Inference orchestrator
│   ├── api/
│   │   └── routes.py                  # POST /predict, GET /health, GET /records
│   └── storage/
│       ├── database.py                # Async SQLAlchemy engine + session
│       └── models.py                  # PredictionRecord ORM model
├── training/
│   ├── data_generator.py              # Synthetic EHR dataset generator
│   ├── train.py                       # End-to-end training pipeline
│   ├── evaluate.py                    # Metrics: accuracy, recall, F1, ROC-AUC
│   └── ablation.py                    # Structured-only / NLP-only / Hybrid study
├── tests/
│   ├── test_ingestion.py              # Layer 1 unit tests
│   ├── test_processing.py             # Layer 2 unit tests
│   ├── test_model.py                  # Layer 3 unit tests
│   └── test_output.py                 # Layer 4 unit tests (mocked NLP)
├── artifacts/                         # Saved model artifacts
├── logs/                              # JSON log files
├── requirements.txt
├── .env.example
├── setup_venv.bat                     # Windows venv + dependency setup
└── setup_venv.sh                      # Linux/macOS venv + dependency setup
```

---

## Structured Feature Schema (Authoritative)

All 16 variables are ordinal categorical, integer scale **0–3** (0 = None/Normal, 3 = Severe).

| Index | Feature                 | Category             |
| ----- | ----------------------- | -------------------- |
| 0     | `mood_swings`           | Psychological State  |
| 1     | `anxiety_level`         | Psychological State  |
| 2     | `depression_indicators` | Psychological State  |
| 3     | `emotional_stability`   | Psychological State  |
| 4     | `days_indoors`          | Behavioural Patterns |
| 5     | `social_interaction`    | Behavioural Patterns |
| 6     | `activity_level`        | Behavioural Patterns |
| 7     | `sleep_quality`         | Behavioural Patterns |
| 8     | `coping_struggles`      | Coping & Stress      |
| 9     | `stress_level`          | Coping & Stress      |
| 10    | `work_engagement`       | Coping & Stress      |
| 11    | `motivation_level`      | Coping & Stress      |
| 12    | `concentration_level`   | Cognitive Function   |
| 13    | `decision_difficulty`   | Cognitive Function   |
| 14    | `memory_issues`         | Cognitive Function   |
| 15    | `support_system`        | Social Context       |

**Schema change protocol:** Any addition, removal, or reordering requires updates to:

- `app/layers/ingestion/schemas.py` (Pydantic model)
- `app/layers/processing/structured_processor.py` (`FEATURE_ORDER`)
- `app/layers/model/fusion_layer.py` (dimension documentation)
- This README table

---

## Hybrid Feature Vector Layout

```
hybrid_vector = concat(embedding_vector, structured_vector)
             = [ embedding[0:768] | structured[768:784] ]
               └── ClinicalBERT CLS ──┘└── 16 features ─┘
               total: 784 dimensions
```

---

## Setup & Installation

### Prerequisites

- Python 3.10+
- PostgreSQL 14+

### Windows

```bat
setup_venv.bat
```

### Linux / macOS

```bash
chmod +x setup_venv.sh && ./setup_venv.sh
```

### Manual

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

---

## Configuration

```bash
cp .env.example .env
```

Edit `.env`:

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/ehr_db
CLINICALBERT_MODEL=medicalai/ClinicalBERT
DISTRESS_CLASS_WEIGHT=3.0
ATTENTION_TOP_K=10
LOG_LEVEL=INFO
```

---

## Training

### Synthetic data (default — no dataset required)

```bash
python -m training.train --samples 1000 --distress-ratio 0.20
```

### Real data (CSV format)

CSV must contain columns: `patient_id, clinical_text, label` (0=Stable, 1=Distress) + all 16 feature columns.

```bash
python -m training.train --csv data/your_dataset.csv
```

### Ablation study

Trains and compares Structured-Only, NLP-Only, and Hybrid variants:

```bash
python -m training.ablation --samples 800
```

Results are printed to stdout and saved to `artifacts/ablation_report.txt`.

---

## Running the API Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive docs: http://localhost:8000/docs

---

## API Reference

### POST `/api/v1/predict`

**Request body:**

```json
{
  "patient_id": "PT00042",
  "timestamp": "2026-04-27T09:15:00",
  "clinical_text": "Patient reports extreme anxiety and cannot sleep. Does not leave the house.",
  "structured": {
    "mood_swings": 3,
    "anxiety_level": 3,
    "depression_indicators": 2,
    "emotional_stability": 2,
    "days_indoors": 3,
    "social_interaction": 2,
    "activity_level": 1,
    "sleep_quality": 3,
    "coping_struggles": 3,
    "stress_level": 3,
    "work_engagement": 1,
    "motivation_level": 2,
    "concentration_level": 2,
    "decision_difficulty": 2,
    "memory_issues": 1,
    "support_system": 1
  }
}
```

**Response:**

```json
{
  "patient_id": "PT00042",
  "prediction": "Distress",
  "confidence_score": 0.93,
  "important_tokens": [
    { "word": "anxious", "weight": 0.87 },
    { "word": "not_sleep", "weight": 0.82 },
    { "word": "isolated", "weight": 0.74 }
  ]
}
```

### GET `/api/v1/health`

Returns pipeline readiness and server timestamp.

### GET `/api/v1/records`

Paginated audit log. Query params: `patient_id`, `limit` (max 100), `offset`.

---

## Performance Targets

| Metric            | Target   | Notes                                                |
| ----------------- | -------- | ---------------------------------------------------- |
| Recall (Distress) | ≥ 0.90   | **Priority metric** — minimise false negatives       |
| Accuracy          | ≥ 0.85   | —                                                    |
| Latency           | ≤ 120 ms | Per-instance; requires GPU for consistent compliance |

> **Note on latency:** ClinicalBERT inference on CPU typically takes 200–400 ms. GPU deployment (CUDA) reduces this to under 30 ms. For CPU-only environments, consider model quantization (`torch.quantization`) or using a distilled BERT variant.

---

## Class Imbalance Handling

| Method                  | Where         | Implementation                                                  |
| ----------------------- | ------------- | --------------------------------------------------------------- |
| **SMOTE**               | Training data | `imbalanced-learn` applied to hybrid vectors before training    |
| **Class-weighted loss** | Model level   | `class_weight={0: 1.0, 1: DISTRESS_CLASS_WEIGHT}` in RF and SVM |

`DISTRESS_CLASS_WEIGHT` defaults to `3.0` (configurable via `.env`).

---

## Explainability (XAI)

Every prediction is accompanied by an attention-based explanation. Attention weights from all transformer layers and heads are averaged, then mapped back to whole words (WordPiece sub-tokens are merged). The top-k most attended words are returned with normalised scores.

Negation markers (`NEG_` from preprocessing) are rendered as `not_<word>` in the token output, preserving clinical polarity.

---

## Running Tests

```bash
pytest tests/ -v
```

Tests that require ClinicalBERT (NLP engine) are mocked to run offline. All four layers have independent test coverage.

---

## Constraints

| Rule                                    | Status                                                  |
| --------------------------------------- | ------------------------------------------------------- |
| No silent preprocessing                 | ✅ Every step logs its transformation                   |
| No dropped negations                    | ✅ `preserve_negations()` retains all negation triggers |
| No schema changes without documentation | ✅ Schema change protocol documented above              |
| No black-box outputs without XAI        | ✅ Every prediction includes `important_tokens`         |

---

## Database Schema

All inference events are stored in `prediction_records` for clinical auditability:

| Column                    | Type        | Description                       |
| ------------------------- | ----------- | --------------------------------- |
| `patient_id`              | VARCHAR     | Patient identifier                |
| `request_timestamp`       | TIMESTAMPTZ | Timestamp from the request        |
| `raw_clinical_text`       | TEXT        | Original unprocessed note         |
| `raw_structured_features` | JSONB       | Original structured payload       |
| `cleaned_text`            | TEXT        | After full preprocessing pipeline |
| `normalised_structured`   | JSONB       | MinMax-normalised feature map     |
| `prediction`              | VARCHAR     | "Distress" or "Stable"            |
| `confidence_score`        | FLOAT       | Probability of predicted class    |
| `important_tokens`        | JSONB       | XAI token-weight list             |
| `sentiment`               | VARCHAR     | Coarse NLP sentiment label        |
| `latency_ms`              | FLOAT       | Inference time in milliseconds    |
