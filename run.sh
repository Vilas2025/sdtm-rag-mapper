#!/bin/bash
# Quick-start script for SDTM RAG Mapper
# Usage: bash run.sh

set -e

if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and add your OpenAI key."
    exit 1
fi

# Load env
export $(grep -v '^#' .env | xargs)

# Build the index if it doesn't exist
if [ ! -f data/sdtm_faiss.index ]; then
    echo "Building vector index (one-time setup)..."
    python -m backend.build_index
fi

# Start API in background
echo "Starting FastAPI on :8000..."
uvicorn backend.api:app --port 8000 --reload &
API_PID=$!

# Trap to clean up the API when the script exits
trap "kill $API_PID 2>/dev/null" EXIT

# Wait a moment for API to come up
sleep 3

# Start Streamlit (foreground)
echo "Starting Streamlit UI on :8501..."
streamlit run frontend/app.py
