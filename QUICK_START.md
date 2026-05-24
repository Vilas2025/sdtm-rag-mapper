# SDTM-RAG: OpenAI → Ollama - Quick Setup (3 Steps)

## ⚡ TL;DR - Get Running in 5 Minutes

### Step 1: Install & Run Ollama
```bash
# Install (macOS)
brew install ollama

# Pull llama3 model
ollama pull llama3

# Start service (keep this terminal open)
ollama serve
```

### Step 2: Start Backend (New Terminal)
```bash
cd /Users/vilasjadhav/Downloads/sdtm-rag
source venv/bin/activate
uvicorn backend.api:app --reload --host 127.0.0.1 --port 8001
```

### Step 3: Test It Works
```bash
# Should return: {"status":"ok","index_loaded":true,"ollama_available":true,"llm_backend":"ollama"}
curl http://127.0.0.1:8001/health | python3 -m json.tool
```

---

## What Changed

| Component | Before | After |
|-----------|--------|-------|
| **LLM** | OpenAI GPT-4 (API) | Ollama Llama3 (Local) |
| **Cost** | Per API call ($) | Free (0$) |
| **API Key** | Required `OPENAI_API_KEY` | Not needed ❌ |
| **Response Format** | Same | Same ✅ |
| **RAG** | FAISS + Embeddings | FAISS + Embeddings ✅ |
| **Frontend** | Works as-is | Works as-is ✅ |

---

## Files Modified

1. **requirements.txt** - Removed `openai==2.37.0`
2. **backend/mapper.py** - Replaced OpenAI with Ollama API calls
3. **backend/api.py** - Updated health check, removed OpenAI check
4. **frontend/app.py** - No changes (works as-before)

---

## Test the /map Endpoint

```bash
# Test with sample variable
curl -X POST http://127.0.0.1:8001/map \
  -H "Content-Type: application/json" \
  -d '{
    "name": "patient_age",
    "description": "Age of patient at baseline visit",
    "sample_values": ["25", "45", "67", "32", "78"]
  }' 2>&1 | python3 -m json.tool
```

**Expected output**: JSON with `domain_code`, `variable_name`, `confidence`, `reasoning`, etc.
**Timing**: First call ~20-30s, subsequent calls ~5-15s

---

## Troubleshooting

❌ **"Cannot connect to Ollama"**  
→ Check `ollama serve` is running in another terminal

❌ **"Model not found"**  
→ Run `ollama pull llama3`

❌ **Request timeout**  
→ Normal - first request loads LLM model, be patient (30s)

---

## One-Liner to Test Everything

```bash
# Terminal 1: Ollama
ollama pull llama3 && ollama serve

# Terminal 2: Backend  
cd /Users/vilasjadhav/Downloads/sdtm-rag && source venv/bin/activate && uvicorn backend.api:app --reload --host 127.0.0.1 --port 8001

# Terminal 3: Test
sleep 5 && curl http://127.0.0.1:8001/health
```

---

## Full Details

See `OLLAMA_MIGRATION_GUIDE.md` for comprehensive docs.
