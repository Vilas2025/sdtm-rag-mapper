"""
SDTM Mapper
-----------
Combines retrieval (FAISS) with Ollama (local LLM) to produce structured mapping suggestions
for raw clinical variables. Returns mappings with confidence and citations.
"""

import json
import requests
from typing import List, Dict, Any
from backend.vector_store import SDTMVectorStore


OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"

SYSTEM_PROMPT = """You are an expert in CDISC SDTM (Study Data Tabulation Model) mapping.
Your job is to map a raw clinical variable to the most appropriate SDTM domain and variable.

You will receive:
- A raw variable name, description, and sample values
- Retrieved context from the CDISC SDTM Implementation Guide

Your output MUST be ONLY a single valid JSON object. No explanations, no markdown fences, no text before or after.

CRITICAL: Return ONLY valid JSON, nothing else.

JSON Schema:
{
  "domain_code": "<two-letter SDTM domain code, e.g. DM, AE, VS>",
  "variable_name": "<SDTM variable name, e.g. USUBJID, AETERM>",
  "variable_label": "<the official SDTM variable label>",
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<concise explanation, 1-3 sentences, of why this mapping is correct>",
  "citation": "<the source string from the retrieved context that supports this mapping>",
  "alternative_mappings": [
    {"domain_code": "...", "variable_name": "...", "reason": "..."}
  ]
}

Rules:
- Use ONLY domain codes and variable names that appear in the retrieved context.
- If no good mapping exists in the retrieved context, set confidence to 0.0 and explain why.
- Confidence should reflect how clearly the raw variable matches an SDTM variable.
- Include up to 2 alternatives if there's reasonable ambiguity.
- Return ONLY the JSON object. No other text whatsoever.
"""


def format_context(retrieved: List[Dict[str, Any]]) -> str:
    """Format retrieved chunks into a context block for the LLM."""
    blocks = []
    for i, chunk in enumerate(retrieved, start=1):
        block = f"[{i}] Source: {chunk['source']}\n{chunk['text']}"
        blocks.append(block)
    return "\n\n".join(blocks)


def format_user_query(
    raw_name: str,
    description: str,
    sample_values: List[str],
    context: str,
) -> str:
    """Format the user message for the mapping call."""
    return f"""Raw variable to map:
- Name: {raw_name}
- Description: {description}
- Sample values: {', '.join(str(v) for v in sample_values[:5])}

Retrieved SDTM context:
{context}

Produce the JSON mapping object now."""


def call_ollama(prompt: str) -> str:
    """Call Ollama local API and return the response text."""
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.1,
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json().get("response", "")
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"Cannot connect to Ollama at {OLLAMA_URL}. "
            "Make sure Ollama is running: ollama serve"
        )
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Ollama API error: {e}")


def extract_json_from_text(text: str) -> Dict[str, Any]:
    """Extract and parse JSON object from text that may contain extra content.
    
    Handles cases where the LLM returns text like:
    "Here is the mapping...
    { ...json... }
    Note that..."
    
    Args:
        text: Raw text that may contain JSON somewhere
        
    Returns:
        Parsed JSON object
        
    Raises:
        json.JSONDecodeError: If no valid JSON found or parsing fails
    """
    text = text.strip()
    
    # Find the first '{' and last '}'
    start_idx = text.find('{')
    end_idx = text.rfind('}')
    
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        raise json.JSONDecodeError("No JSON object found in text", text, 0)
    
    # Extract the substring between first '{' and last '}'
    json_str = text[start_idx:end_idx + 1]
    
    # Parse the JSON
    return json.loads(json_str)


def normalize_mapping_response(mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize LLM response by mapping field names to expected output format.
    
    Maps:
    - variable_label -> label
    - citation -> source_citation
    """
    # Map field names
    if "variable_label" in mapping and "label" not in mapping:
        mapping["label"] = mapping.pop("variable_label")
    
    if "citation" in mapping and "source_citation" not in mapping:
        mapping["source_citation"] = mapping.pop("citation")
    
    return mapping


class SDTMMapper:
    """Maps raw clinical variables to SDTM variables using RAG + local Ollama LLM."""

    def __init__(
        self,
        vector_store: SDTMVectorStore,
        model: str = OLLAMA_MODEL,
        top_k: int = 6,
    ):
        self.store = vector_store
        self.model = model
        self.top_k = top_k

    def map_variable(
        self,
        raw_name: str,
        description: str,
        sample_values: List[str],
    ) -> Dict[str, Any]:
        """Map a single raw variable to an SDTM variable."""
        # Build retrieval query from name + description (most informative combo)
        query = f"{raw_name} {description}"
        retrieved = self.store.search(query, k=self.top_k)
        context = format_context(retrieved)

        user_msg = format_user_query(raw_name, description, sample_values, context)
        
        # Combine system prompt and user message for Ollama
        full_prompt = f"{SYSTEM_PROMPT}\n\n{user_msg}"

        try:
            raw_output = call_ollama(full_prompt)
        except RuntimeError as e:
            return {
                "error": str(e),
                "raw_variable": {
                    "name": raw_name,
                    "description": description,
                    "sample_values": sample_values,
                }
            }

        # Try to extract and parse JSON from raw output
        try:
            mapping = extract_json_from_text(raw_output)
        except json.JSONDecodeError as e:
            # If parsing fails, return fallback response with raw output for debugging
            return {
                "error": "Failed to parse LLM output as JSON",
                "raw_output": raw_output[:500],  # Include first 500 chars for debugging
                "exception": str(e),
                "domain_code": "UNKNOWN",
                "variable_name": raw_name,
                "label": f"Mapping for {raw_name}",
                "confidence": 0.0,
                "reasoning": "Parser error - unable to extract JSON from LLM response",
                "source_citation": "N/A",
                "raw_variable": {
                    "name": raw_name,
                    "description": description,
                    "sample_values": sample_values,
                }
            }

        # Normalize field names
        mapping = normalize_mapping_response(mapping)

        # Attach the retrieval evidence so the UI can show what was used
        mapping["retrieved_chunks"] = [
            {
                "source": c["source"],
                "text": c["text"],
                "score": c["score"],
                "type": c.get("type"),
                "domain_code": c.get("domain_code"),
                "variable_name": c.get("variable_name"),
            }
            for c in retrieved
        ]
        mapping["raw_variable"] = {
            "name": raw_name,
            "description": description,
            "sample_values": sample_values,
        }
        return mapping

    def map_batch(self, variables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Map a list of raw variables. Each item needs name, description, sample_values."""
        results = []
        for var in variables:
            result = self.map_variable(
                raw_name=var["name"],
                description=var.get("description", ""),
                sample_values=var.get("sample_values", []),
            )
            results.append(result)
        return results
