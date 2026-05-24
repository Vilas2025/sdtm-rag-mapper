# SDTM-RAG: OpenAI → Ollama Migration Guide

## Summary of Changes

Your SDTM-RAG project has been successfully migrated from OpenAI to **Ollama** (local LLM). No more API quotas or costs! 🎉

---

## Files Changed

### 1. **requirements.txt**
- **Removed**: `openai==1.51.0` (or 2.37.0)
- **Added**: Nothing (requests is already there)
- **Result**: Project now only needs `requests` for Ollama API calls

### 2. **backend/mapper.py** (Major changes)
- **Removed**:
  - `from openai import OpenAI`
  - OpenAI client initialization requiring API key
  
- **Added**:
  - `import requests`
  - `call_ollama()` function that POSTs to `http://localhost:11434/api/generate`
  - Ollama model name: `llama3`
  - Local LLM integration with error handling
  
- **Key functions**:
  - `call_ollama(prompt)`: Sends prompt to Ollama, returns response
  - `SDTMMapper.__init__()`: No longer requires OPENAI_API_KEY
  - `map_variable()`: Uses Ollama instead of OpenAI Chat API

### 3. **backend/api.py** (Minor changes)
- **Removed**:
  - `os.getenv("OPENAI_API_KEY")` from health check
  - `"openai_key_set"` status field
  
- **Added**:
  - `is_ollama_available()` function to check if Ollama is running
  - `"ollama_available"` status in `/health` endpoint
  - `"llm_backend": "ollama"` field in `/health` response
  - Import `requests` and `OLLAMA_URL`, `OLLAMA_MODEL` from mapper
  
- **Health endpoint now returns**:
  ```json
  {
    "status": "ok",
    "index_loaded": true/false,
    "ollama_available": true/false,
    "llm_backend": "ollama"
  }
  ```

### 4. **frontend/app.py**
- **No changes** - Frontend works exactly as before
- Displays the same UI with the same response format

---

## Installation & Setup

### Step 1: Install Ollama

**macOS:**
```bash
# Download from official site
curl -fsSL https://ollama.ai/install.sh | sh

# Or use Homebrew
brew install ollama
```

**Linux:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**Windows:**
- Download installer from https://ollama.ai

### Step 2: Pull the llama3 Model

```bash
# Start Ollama service first (if not auto-started)
ollama serve

# In a NEW terminal, pull the model
ollama pull llama3

# Verify it's installed
ollama list
```

Expected output after `ollama list`:
```
NAME         ID              SIZE     MODIFIED
llama3       a6eb4a78af83    4.7 GB   2 minutes ago
```

### Step 3: Verify Ollama is Running

```bash
# Check if Ollama service is listening on port 11434
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3", "prompt": "hello", "stream": false}' 2>&1 | head -20

# You should see a JSON response with "response" field
```

---

## Running the Project

### Terminal 1: Start Ollama Service
```bash
ollama serve
```
Keep this running. Output should show:
```
[GIN-debug] Loaded HTML Templates (0): 
[GIN-debug] Loaded error Templates (0): 
[GIN] Listen and serve on 127.0.0.1:11434
```

### Terminal 2: Start Backend API
```bash
cd /Users/vilasjadhav/Downloads/sdtm-rag
source venv/bin/activate
uvicorn backend.api:app --reload --host 127.0.0.1 --port 8001
```

### Terminal 3: Start Frontend (Optional)
```bash
cd /Users/vilasjadhav/Downloads/sdtm-rag/frontend
source ../venv/bin/activate
streamlit run app.py
```

---

## Testing

### 1. Health Check Endpoint

```bash
curl -X GET http://127.0.0.1:8001/health
```

**Expected response:**
```json
{
  "status": "ok",
  "index_loaded": true,
  "ollama_available": true,
  "llm_backend": "ollama"
}
```

### 2. Test /map Endpoint (requires Ollama running)

```bash
curl -X POST http://127.0.0.1:8001/map \
  -H "Content-Type: application/json" \
  -d '{
    "name": "age_years",
    "description": "Patient age in years at baseline",
    "sample_values": ["25", "45", "67", "32", "78"]
  }' 2>&1 | python3 -m json.tool
```

**Expected response** (first request may take 20-30 seconds for LLM processing):
```json
{
  "domain_code": "DM",
  "variable_name": "AGE",
  "variable_label": "Age",
  "confidence": 0.95,
  "reasoning": "Age is a standard SDTM demographic variable...",
  "citation": "[1] Source: CDISC SDTM IG - DM Domain",
  "retrieved_chunks": [...],
  "raw_variable": {
    "name": "age_years",
    "description": "Patient age in years at baseline",
    "sample_values": ["25", "45", "67", "32", "78"]
  }
}
```

### 3. Test /map/batch Endpoint

```bash
curl -X POST http://127.0.0.1:8001/map/batch \
  -H "Content-Type: application/json" \
  -d '{
    "variables": [
      {
        "name": "age_years",
        "description": "Patient age in years",
        "sample_values": ["25", "45", "67"]
      },
      {
        "name": "visit_date",
        "description": "Date of patient visit",
        "sample_values": ["2023-01-01", "2023-02-15"]
      }
    ]
  }' 2>&1 | python3 -m json.tool
```

---

## Performance Notes

| Aspect | Details |
|--------|---------|
| **First Request** | ~20-30 seconds (LLM context loading) |
| **Subsequent Requests** | ~5-15 seconds (model stays in memory) |
| **Response Format** | Identical to OpenAI version |
| **Cost** | $0 (local, no API calls) |
| **Dependencies** | Only Ollama service + requests library |

---

## Troubleshooting

### Issue: "Cannot connect to Ollama at http://localhost:11434"

**Solution:**
1. Make sure Ollama service is running: `ollama serve`
2. Check port 11434 is listening: `lsof -i :11434`
3. Test connectivity: `curl http://localhost:11434/api/generate -X POST`

### Issue: "Model not found" error

**Solution:**
```bash
ollama pull llama3
ollama list  # verify it's installed
```

### Issue: Backend takes too long to respond

**Solution:**
- First request may take 20-30 seconds while LLM loads context
- Model stays in memory after first use, subsequent requests are faster
- If timeout occurs, increase request timeout in frontend

### Issue: Response doesn't have JSON structure

**Solution:**
- Ollama might be returning plain text or error
- Check: `curl -X POST http://localhost:11434/api/generate -H "Content-Type: application/json" -d '{"model": "llama3", "prompt": "test", "stream": false}'`

---

## API Response Format

The response format remains **identical** to the OpenAI version:

```python
{
    "domain_code": str,           # e.g., "DM", "AE", "VS"
    "variable_name": str,         # e.g., "AGE", "AETERM"
    "variable_label": str,        # Official SDTM variable label
    "confidence": float,          # 0.0 to 1.0
    "reasoning": str,             # Why this mapping was chosen
    "citation": str,              # Retrieved source context
    "alternative_mappings": [],   # Alternative suggestions
    "retrieved_chunks": [],       # RAG context used
    "raw_variable": {             # Original input
        "name": str,
        "description": str,
        "sample_values": []
    }
}
```

---

## Uninstalling OpenAI Dependency

The OpenAI package has been removed from requirements.txt. To clean up:

```bash
# Completely remove OpenAI from venv
pip uninstall -y openai

# Verify it's gone
pip list | grep openai  # Should return nothing
```

---

## Quick Reference: Command Checklist

```bash
# 1. Install Ollama
brew install ollama  # macOS

# 2. Pull model (one-time)
ollama pull llama3

# 3. Start Ollama service (keep running)
ollama serve

# 4. In new terminal: Start backend
cd /Users/vilasjadhav/Downloads/sdtm-rag
source venv/bin/activate
uvicorn backend.api:app --reload --host 127.0.0.1 --port 8001

# 5. Test health endpoint
curl http://127.0.0.1:8001/health

# 6. Test mapping endpoint
curl -X POST http://127.0.0.1:8001/map \
  -H "Content-Type: application/json" \
  -d '{"name":"age_years","description":"Age in years","sample_values":["25","45","67"]}'
```

---

## Summary of Benefits

✅ **No more API quotas** - Run locally  
✅ **Zero cost** - No OpenAI charges  
✅ **Privacy** - All processing is local  
✅ **Same response format** - Frontend works unchanged  
✅ **Fast RAG** - FAISS + sentence-transformers still working  
✅ **Easy setup** - Just `ollama pull llama3`  

---

## Need Help?

Check the Ollama docs: https://github.com/ollama/ollama
Check FAISS docs: https://faiss.ai/

Happy mapping! 🧬📊
