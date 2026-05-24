"""
FastAPI backend for the SDTM RAG mapper with Ollama local LLM.

Endpoints:
  POST /map               - Map a single raw variable
  POST /map/batch         - Map a list of raw variables
  POST /feedback          - Log a reviewer's decision
  GET  /feedback/stats    - Retrieve aggregate metrics
  GET  /feedback          - Retrieve full feedback log
  GET  /examples          - Get synthetic raw-data examples
  GET  /health            - Health check

Run with:
    uvicorn backend.api:app --reload --port 8001
"""

import json
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.vector_store import SDTMVectorStore
from backend.mapper import SDTMMapper, OLLAMA_URL, OLLAMA_MODEL
from backend import feedback_store


DATA_DIR = Path(__file__).parent.parent / "data"


# --------- Pydantic models ----------------------------------------------------

class RawVariable(BaseModel):
    name: str
    description: str = ""
    sample_values: List[str] = Field(default_factory=list)


class BatchMapRequest(BaseModel):
    variables: List[RawVariable]


class FeedbackRequest(BaseModel):
    raw_variable: Dict[str, Any]
    suggestion: Dict[str, Any]
    decision: str  # 'accept' | 'edit' | 'reject'
    final_domain: Optional[str] = None
    final_variable: Optional[str] = None
    reviewer_note: Optional[str] = None


# --------- App setup ----------------------------------------------------------

app = FastAPI(
    title="SDTM RAG Mapper",
    description="RAG-powered mapping of raw clinical data to CDISC SDTM standards (Ollama-powered).",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy-init globals
_store: Optional[SDTMVectorStore] = None
_mapper: Optional[SDTMMapper] = None


@app.on_event("startup")
async def startup_event():
    """Initialize vector store and mapper on FastAPI startup."""
    global _store, _mapper
    print("[startup] Initializing FAISS vector store...")
    _store = SDTMVectorStore()
    _store.load()
    print("[startup] Vector store loaded successfully.")
    print("[startup] Initializing mapper...")
    _mapper = SDTMMapper(vector_store=_store)
    print("[startup] Mapper initialized successfully.")


def get_store() -> SDTMVectorStore:
    """Return the initialized vector store."""
    return _store


def get_mapper() -> SDTMMapper:
    """Return the initialized mapper."""
    return _mapper


def is_ollama_available() -> bool:
    """Check if Ollama is running and the model is available."""
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": "test", "stream": False},
            timeout=5,
        )
        return response.status_code == 200
    except Exception:
        return False


# --------- Endpoints ----------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "index_loaded": _store is not None and _store.index is not None,
        "ollama_available": is_ollama_available(),
        "llm_backend": "ollama",
    }


@app.post("/map")
def map_variable(var: RawVariable):
    try:
        mapper = get_mapper()
        result = mapper.map_variable(
            raw_name=var.name,
            description=var.description,
            sample_values=var.sample_values,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/map/batch")
def map_batch(req: BatchMapRequest):
    try:
        mapper = get_mapper()
        results = mapper.map_batch(
            [v.model_dump() for v in req.variables]
        )
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/feedback")
def post_feedback(req: FeedbackRequest):
    try:
        row_id = feedback_store.log_feedback(
            raw_variable=req.raw_variable,
            suggestion=req.suggestion,
            decision=req.decision,
            final_domain=req.final_domain,
            final_variable=req.final_variable,
            reviewer_note=req.reviewer_note,
        )
        return {"status": "logged", "id": row_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/feedback/stats")
def feedback_stats():
    return feedback_store.get_stats()


@app.get("/feedback")
def feedback_list():
    return {"feedback": feedback_store.get_all_feedback()}


@app.get("/examples")
def get_examples():
    examples_path = DATA_DIR / "synthetic_raw_data.json"
    with open(examples_path) as f:
        return json.load(f)
