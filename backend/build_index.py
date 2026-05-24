"""
One-time index builder. Run this once before starting the API.

Usage:
    python -m backend.build_index
"""
from pathlib import Path
from backend.vector_store import SDTMVectorStore

DATA_DIR = Path(__file__).parent.parent / "data"
KB_PATH = DATA_DIR / "sdtm_knowledge_base.json"


def main():
    print("Building SDTM vector store...")
    store = SDTMVectorStore()
    store.build(KB_PATH)
    store.save()
    print(f"  Indexed {len(store.chunks)} chunks")
    print(f"  Index saved to {DATA_DIR / 'sdtm_faiss.index'}")
    print(f"  Chunks saved to {DATA_DIR / 'sdtm_chunks.pkl'}")
    print("Done.")


if __name__ == "__main__":
    main()
