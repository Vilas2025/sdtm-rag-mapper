# SDTM RAG Mapper

Retrieval-augmented mapping of raw clinical data variables to CDISC SDTM standards, with a human-in-the-loop feedback layer.

This prototype mirrors the AbbVie production work: a domain-specific LLM pipeline using LangChain-style retrieval over CDISC SDTM Implementation Guide content, FAISS for vector search, OpenAI as the reasoning LLM, and SQLite-logged reviewer decisions that close the loop on accuracy improvement.

## What it does

Given a raw clinical variable (e.g. `patient_age` with sample values `54, 62, 47`), the system:

1. **Retrieves** relevant SDTM domain and variable documentation from a FAISS vector index built over CDISC content.
2. **Suggests a mapping** (`domain_code`, `variable_name`, confidence, reasoning, source citation) using an LLM grounded in the retrieved context.
3. **Lets a reviewer accept / edit / reject** the suggestion through a Streamlit UI.
4. **Logs every decision** to a SQLite store so accuracy can be measured over time and edits can feed back into the system.

## Architecture

```
┌─────────────────────┐
│  Streamlit UI       │  ← reviewer accepts / edits / rejects
│  (frontend/app.py)  │
└──────────┬──────────┘
           │ HTTP
┌──────────▼──────────┐
│  FastAPI            │
│  (backend/api.py)   │
└─────┬───────┬───────┘
      │       │
      │       └────────┐
      │                ▼
      │     ┌───────────────────┐
      │     │ feedback_store.py │  → SQLite (data/feedback.db)
      │     └───────────────────┘
      ▼
┌─────────────────────┐
│   mapper.py         │  ← orchestrates retrieval + LLM
└─────┬───────────┬───┘
      │           │
      ▼           ▼
┌──────────┐  ┌────────────┐
│  FAISS   │  │  OpenAI    │
│  index   │  │  GPT-4o    │
│ (MiniLM) │  │            │
└──────────┘  └────────────┘
      ▲
      │
┌─────┴────────────────┐
│ sdtm_knowledge_base  │  CDISC SDTM IG content (6 domains: DM, AE, VS, LB, CM, EX)
└──────────────────────┘
```

## Quick start

```bash
# 1. Install
python -m venv venv
source venv/bin/activate           # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Add your OpenAI key
cp .env.example .env
# edit .env, paste your key

# 3. Build the FAISS index (one-time)
python -m backend.build_index

# 4. Start API and UI together
bash run.sh
```

Then open http://localhost:8501

## Running components individually

```bash
# Just the API (for testing or non-UI usage)
uvicorn backend.api:app --reload --port 8000

# Just the UI (the UI expects API on :8000)
streamlit run frontend/app.py
```

## API endpoints

| Method | Path                | Purpose                                       |
|--------|---------------------|-----------------------------------------------|
| POST   | `/map`              | Map a single raw variable                     |
| POST   | `/map/batch`        | Map a list of raw variables                   |
| POST   | `/feedback`         | Log a reviewer decision                       |
| GET    | `/feedback/stats`   | Aggregate metrics (acceptance rate, etc.)     |
| GET    | `/feedback`         | All logged feedback                           |
| GET    | `/examples`         | Synthetic raw-data examples for testing       |
| GET    | `/health`           | Health check                                  |

### Example request

```bash
curl -X POST http://localhost:8000/map \
  -H "Content-Type: application/json" \
  -d '{
    "name": "sys_bp",
    "description": "Systolic blood pressure in mmHg",
    "sample_values": ["128", "124", "142"]
  }'
```

### Example response

```json
{
  "domain_code": "VS",
  "variable_name": "VSORRES",
  "variable_label": "Result or Finding in Original Units",
  "confidence": 0.92,
  "reasoning": "The variable holds blood pressure measurements in their original collected form. In SDTM Vital Signs (VS), original-unit results map to VSORRES with VSTESTCD=SYSBP indicating the test type.",
  "citation": "CDISC SDTM IG - VS Domain",
  "alternative_mappings": [
    {"domain_code": "VS", "variable_name": "VSSTRESN", "reason": "If values have been standardized to numeric form"}
  ],
  "retrieved_chunks": [...]
}
```

## Project structure

```
sdtm-rag/
├── backend/
│   ├── __init__.py
│   ├── api.py              # FastAPI app
│   ├── mapper.py           # RAG + LLM mapping logic
│   ├── vector_store.py     # FAISS + sentence-transformers
│   ├── feedback_store.py   # SQLite feedback log
│   └── build_index.py      # One-time index builder
├── frontend/
│   └── app.py              # Streamlit UI
├── data/
│   ├── sdtm_knowledge_base.json   # CDISC domain definitions
│   ├── synthetic_raw_data.json    # Example CRF variables
│   ├── sdtm_faiss.index           # (generated)
│   ├── sdtm_chunks.pkl            # (generated)
│   └── feedback.db                # (generated)
├── requirements.txt
├── run.sh
├── .env.example
└── README.md
```

## How accuracy improves over time

The bullet on the resume — "improving SDTM mapping accuracy by 25% with human-in-the-loop feedback" — corresponds to this loop:

1. Every reviewer decision (accept / edit / reject) is logged with the original suggestion.
2. The **acceptance rate** is the headline accuracy metric, visible on the dashboard.
3. **Edits** are the gold signal: they tell you what the model got wrong and what the correct mapping was. In a production system these would feed:
   - **Few-shot examples** added to the prompt for similar future queries
   - **Retrieval reweighting** to surface the correct chunks more strongly
   - A periodic **fine-tuning dataset** (LoRA-style) for the base mapping model
4. **Rejections** are the signal that the knowledge base needs to grow — a raw variable that legitimately doesn't map to anything is a flag to add a new domain or document an edge case.

The prototype logs the data and surfaces the metric. The next iteration would wire the edits back into the prompt as few-shots.

## Limitations of this prototype

- **Knowledge base coverage** is six common domains (DM, AE, VS, LB, CM, EX). Real SDTM IG covers ~40+ domains. Extending is purely a matter of adding to `sdtm_knowledge_base.json`.
- **Single-variable mapping**. Real SDTM mapping often requires joint reasoning across multiple variables (e.g. `bp_value` only makes sense if you know `bp_type` is also being mapped). A future iteration would batch-reason over a full CRF.
- **No automated eval harness yet**. The dashboard shows acceptance rate, but a held-out test set with gold mappings would let you produce the kind of "+25% accuracy" number you can defend.
- **Embedding model is general-purpose** (MiniLM). A domain-tuned embedding model (BGE fine-tuned on CDISC text, for example) would meaningfully improve retrieval quality.

## Where to take it next

In rough priority order:

1. **Eval harness** — a held-out set of (raw variable → gold SDTM mapping) pairs, plus a script that runs the mapper over them and reports top-1 / top-3 accuracy. This is what makes the accuracy claim defensible.
2. **Few-shot from feedback** — when mapping a new variable, retrieve similar past-reviewed variables and include their corrected mappings as in-context examples.
3. **Multi-variable joint mapping** — accept a whole CRF (e.g. CSV upload) and map all variables together, letting the LLM see relationships.
4. **Swap FAISS for Pinecone** in cloud deployment for multi-user persistence.
5. **Add drift monitoring** — the same drift detection pattern used elsewhere on your resume applies here: track shifts in incoming raw-variable distributions and confidence distributions over time.
