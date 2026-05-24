"""
SDTM RAG Vector Store
---------------------
Builds and queries a FAISS index over CDISC SDTM domain documentation.
Uses sentence-transformers for embeddings (no API key required for embeddings).
"""

import json
import os
import pickle
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer


EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DATA_DIR = Path(__file__).parent.parent / "data"
INDEX_PATH = DATA_DIR / "sdtm_faiss.index"
CHUNKS_PATH = DATA_DIR / "sdtm_chunks.pkl"


class SDTMVectorStore:
    """FAISS-backed vector store over SDTM domain documentation."""

    def __init__(self, model_name: str = EMBEDDING_MODEL):
        self.model = SentenceTransformer(model_name)
        self.index: faiss.IndexFlatIP | None = None
        self.chunks: List[Dict[str, Any]] = []

    def _build_chunks(self, knowledge_base: Dict) -> List[Dict[str, Any]]:
        """
        Convert the SDTM knowledge base into retrievable chunks.
        We chunk at two granularities:
          1. Domain-level overview (one per domain)
          2. Variable-level (one per variable, with domain context)
        This lets retrieval surface either the right domain or the right variable.
        """
        chunks = []

        for domain in knowledge_base["domains"]:
            # Domain-level chunk
            domain_text = (
                f"SDTM Domain {domain['domain_code']} - {domain['domain_name']}. "
                f"{domain['description']} "
                f"Guidance: {domain['guidance']}"
            )
            chunks.append({
                "type": "domain",
                "domain_code": domain["domain_code"],
                "domain_name": domain["domain_name"],
                "text": domain_text,
                "source": f"CDISC SDTM IG - {domain['domain_code']} Domain",
                "metadata": {
                    "variables": [v["name"] for v in domain["variables"]],
                    "guidance": domain["guidance"],
                }
            })

            # Variable-level chunks
            for var in domain["variables"]:
                var_text = (
                    f"Variable {var['name']} ({var['label']}) in SDTM domain "
                    f"{domain['domain_code']} ({domain['domain_name']}). "
                    f"Type: {var['type']}. Role: {var['role']}. Core: {var['core']}. "
                    f"Domain context: {domain['description']}"
                )
                chunks.append({
                    "type": "variable",
                    "domain_code": domain["domain_code"],
                    "domain_name": domain["domain_name"],
                    "variable_name": var["name"],
                    "variable_label": var["label"],
                    "text": var_text,
                    "source": f"CDISC SDTM IG - {domain['domain_code']}.{var['name']}",
                    "metadata": var,
                })

        return chunks

    def build(self, knowledge_base_path: str | Path) -> None:
        """Build the FAISS index from the SDTM knowledge base file."""
        with open(knowledge_base_path, "r") as f:
            kb = json.load(f)

        self.chunks = self._build_chunks(kb)
        texts = [c["text"] for c in self.chunks]

        # Encode and normalize for cosine similarity (IP on normalized vectors)
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).astype("float32")

        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(embeddings)

    def save(self) -> None:
        """Persist the index and chunks to disk."""
        if self.index is None:
            raise RuntimeError("Index not built. Call build() first.")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(INDEX_PATH))
        with open(CHUNKS_PATH, "wb") as f:
            pickle.dump(self.chunks, f)

    def load(self) -> None:
        """Load a persisted index and chunks."""
        if not INDEX_PATH.exists() or not CHUNKS_PATH.exists():
            raise FileNotFoundError(
                "Index or chunks not found. Run build_index.py first."
            )
        self.index = faiss.read_index(str(INDEX_PATH))
        with open(CHUNKS_PATH, "rb") as f:
            self.chunks = pickle.load(f)

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve the top-k most relevant chunks for a query."""
        if self.index is None:
            raise RuntimeError("Index not loaded. Call load() or build() first.")

        query_emb = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).astype("float32")

        scores, indices = self.index.search(query_emb, k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            chunk = dict(self.chunks[idx])
            chunk["score"] = float(score)
            results.append(chunk)
        return results
