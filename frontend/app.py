"""
SDTM Mapper - Streamlit UI
--------------------------
Human-in-the-loop interface for reviewing and correcting SDTM mapping suggestions.

Run with:
    streamlit run frontend/app.py
"""

import requests
import streamlit as st
import pandas as pd

API_URL = "http://localhost:8001"

st.set_page_config(
    page_title="SDTM Mapper",
    page_icon="🧬",
    layout="wide",
)

# ---------- Styling -----------------------------------------------------------

st.markdown("""
<style>
    .main-header {
        font-family: 'Georgia', serif;
        font-size: 2.5rem;
        font-weight: 400;
        letter-spacing: -1px;
        color: #1a1a2e;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-family: 'Georgia', serif;
        font-style: italic;
        color: #6b7280;
        font-size: 1.05rem;
        margin-bottom: 2rem;
    }
    .stat-card {
        background: linear-gradient(135deg, #f8fafc 0%, #eef2ff 100%);
        border-left: 3px solid #4338ca;
        padding: 1rem 1.2rem;
        border-radius: 4px;
        margin-bottom: 0.6rem;
    }
    .stat-label {
        font-size: 0.78rem;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .stat-value {
        font-size: 1.8rem;
        font-weight: 600;
        color: #1a1a2e;
    }
    .citation-box {
        background-color: #fefce8;
        border-left: 3px solid #ca8a04;
        padding: 0.6rem 0.9rem;
        border-radius: 3px;
        font-size: 0.85rem;
        color: #422006;
        margin: 0.5rem 0;
    }
    .confidence-high { color: #166534; font-weight: 600; }
    .confidence-med  { color: #92400e; font-weight: 600; }
    .confidence-low  { color: #991b1b; font-weight: 600; }
    .small-muted { color: #6b7280; font-size: 0.82rem; }
</style>
""", unsafe_allow_html=True)

# ---------- Helpers -----------------------------------------------------------

def confidence_class(conf: float) -> str:
    if conf >= 0.8: return "confidence-high"
    if conf >= 0.5: return "confidence-med"
    return "confidence-low"


def confidence_label(conf: float) -> str:
    if conf >= 0.8: return "High"
    if conf >= 0.5: return "Medium"
    return "Low"


def api_get(path: str):
    try:
        return requests.get(f"{API_URL}{path}", timeout=30).json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def api_post(path: str, payload: dict, timeout: int = 60):
    try:
        return requests.post(f"{API_URL}{path}", json=payload, timeout=timeout).json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


# ---------- Sidebar -----------------------------------------------------------

with st.sidebar:
    st.markdown("### Navigation")
    page = st.radio(
        "page_select",
        ["Map Variables", "Examples", "Feedback Dashboard"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("### System Status")
    health = api_get("/health")
    if health:
        status_icon = "🟢" if health.get("status") == "ok" else "🔴"
        st.markdown(f"{status_icon} API: `{health.get('status')}`")
        ollama_icon = "🟢" if health.get("ollama_available") else "🔴"
        st.markdown(f"{ollama_icon} Ollama: `{'available' if health.get('ollama_available') else 'unavailable'}`")
        idx_icon = "🟢" if health.get("index_loaded") else "⚪"
        st.markdown(f"{idx_icon} Vector index: `{'loaded' if health.get('index_loaded') else 'not loaded yet'}`")
    else:
        st.markdown("🔴 API: unreachable")
        st.caption("Start it with: `cd ~/Downloads/sdtm-rag && source venv/bin/activate && uvicorn backend.api:app --port 8001`")

    st.markdown("---")
    st.markdown("### About")
    st.caption(
        "RAG-powered mapping of raw clinical variables to CDISC SDTM standards, "
        "with human-in-the-loop feedback capture."
    )


# ---------- Header ------------------------------------------------------------

st.markdown('<div class="main-header">SDTM Mapper</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Retrieval-augmented mapping of raw clinical data to CDISC SDTM, with human review.</div>',
    unsafe_allow_html=True,
)


# ---------- Page: Map Variables -----------------------------------------------

if page == "Map Variables":
    st.markdown("### Map a raw clinical variable")
    st.caption(
        "Enter a raw variable from your CRF or source data. "
        "The system retrieves relevant CDISC documentation and proposes a mapping."
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        raw_name = st.text_input("Variable name", value="patient_age", placeholder="e.g. patient_age, sys_bp")
        description = st.text_area(
            "Description",
            value="Patient age at consent",
            height=80,
            placeholder="What does this variable represent?",
        )
    with col2:
        sample_values_str = st.text_area(
            "Sample values (one per line)",
            value="54\n62\n47",
            height=140,
            placeholder="Example values from the data",
        )

    if st.button("Map this variable", type="primary"):
        sample_values = [v.strip() for v in sample_values_str.splitlines() if v.strip()]
        with st.spinner("Retrieving context and generating mapping..."):
            result = api_post(
                "/map",
                {"name": raw_name, "description": description, "sample_values": sample_values},
            )

        if result and "error" not in result:
            st.session_state["last_result"] = result
        elif result:
            st.error(f"Mapping failed: {result.get('error')}")
            with st.expander("Raw output"):
                st.code(result.get("raw_output", ""))

    # Display the result if we have one
    if "last_result" in st.session_state:
        result = st.session_state["last_result"]
        st.markdown("---")
        st.markdown("### Suggested mapping")

        col_a, col_b, col_c = st.columns([1, 1, 1])
        conf = float(result.get("confidence", 0))
        cls = confidence_class(conf)
        label = confidence_label(conf)
        with col_a:
            st.markdown(
                f'<div class="stat-card"><div class="stat-label">Domain</div>'
                f'<div class="stat-value">{result.get("domain_code", "—")}</div></div>',
                unsafe_allow_html=True,
            )
        with col_b:
            st.markdown(
                f'<div class="stat-card"><div class="stat-label">Variable</div>'
                f'<div class="stat-value">{result.get("variable_name", "—")}</div></div>',
                unsafe_allow_html=True,
            )
        with col_c:
            st.markdown(
                f'<div class="stat-card"><div class="stat-label">Confidence</div>'
                f'<div class="stat-value {cls}">{conf:.2f} <span style="font-size: 0.95rem;">({label})</span></div></div>',
                unsafe_allow_html=True,
            )

        st.markdown(f"**Label:** {result.get('label') or result.get('variable_label', '—')}")
        st.markdown(f"**Reasoning:** {result.get('reasoning', '—')}")

        st.markdown(
            f'<div class="citation-box"><strong>Source citation:</strong><br/>{result.get("source_citation") or result.get("citation", "—")}</div>',
            unsafe_allow_html=True,
        )

        # Alternatives
        alts = result.get("alternative_mappings") or []
        if alts:
            with st.expander(f"Alternative mappings ({len(alts)})"):
                for alt in alts:
                    st.markdown(
                        f"- **{alt.get('domain_code')}.{alt.get('variable_name')}** — {alt.get('reason', '')}"
                    )

        # Retrieved evidence
        with st.expander("Retrieved evidence (top chunks)"):
            for i, chunk in enumerate(result.get("retrieved_chunks", []), start=1):
                st.markdown(
                    f"**[{i}] {chunk.get('source')}** "
                    f"<span class='small-muted'>(score: {chunk.get('score', 0):.3f})</span>",
                    unsafe_allow_html=True,
                )
                st.caption(chunk.get("text", ""))

        # ----- Human-in-the-loop feedback -----
        st.markdown("---")
        st.markdown("### Reviewer decision")
        st.caption(
            "Your decision is logged and feeds into accuracy metrics. "
            "Edits also serve as training signal for future improvements."
        )

        decision = st.radio(
            "Decision",
            ["accept", "edit", "reject"],
            format_func=lambda x: {
                "accept": "✓ Accept as suggested",
                "edit": "✎ Edit (mapping needs correction)",
                "reject": "✗ Reject (no good mapping)",
            }[x],
            horizontal=True,
        )

        final_domain = result.get("domain_code", "")
        final_variable = result.get("variable_name", "")
        if decision == "edit":
            fc1, fc2 = st.columns(2)
            with fc1:
                final_domain = st.text_input("Corrected domain", value=final_domain)
            with fc2:
                final_variable = st.text_input("Corrected variable", value=final_variable)

        reviewer_note = st.text_input(
            "Note (optional)", placeholder="Why did you make this decision?"
        )

        if st.button("Submit decision", type="primary"):
            payload = {
                "raw_variable": result.get("raw_variable", {}),
                "suggestion": {
                    "domain_code": result.get("domain_code"),
                    "variable_name": result.get("variable_name"),
                    "variable_label": result.get("label") or result.get("variable_label"),
                    "confidence": result.get("confidence"),
                    "reasoning": result.get("reasoning"),
                    "citation": result.get("source_citation") or result.get("citation"),
                },
                "decision": decision,
                "final_domain": final_domain if decision != "reject" else None,
                "final_variable": final_variable if decision != "reject" else None,
                "reviewer_note": reviewer_note or None,
            }
            resp = api_post("/feedback", payload)
            if resp and resp.get("status") == "logged":
                st.success(f"Decision logged (id: {resp.get('id')}). Mapper will learn from this.")
                del st.session_state["last_result"]
                st.rerun()


# ---------- Page: Examples ----------------------------------------------------

elif page == "Examples":
    st.markdown("### Synthetic clinical data examples")
    st.caption(
        "Pre-loaded CRF-style raw data. Click 'Map this' on any variable to test the pipeline."
    )

    examples = api_get("/examples")
    if examples:
        for ex in examples.get("examples", []):
            with st.expander(f"📋 {ex['name']} — {ex['description']}"):
                for var in ex.get("raw_variables", []):
                    cols = st.columns([3, 2, 1])
                    with cols[0]:
                        st.markdown(f"**`{var['name']}`** — {var['description']}")
                        st.caption(f"Samples: {', '.join(var['sample_values'][:3])}")
                    with cols[2]:
                        btn_key = f"map_{ex['id']}_{var['name']}"
                        if st.button("Map this", key=btn_key):
                            with st.spinner("Mapping..."):
                                result = api_post(
                                    "/map",
                                    {
                                        "name": var["name"],
                                        "description": var["description"],
                                        "sample_values": var["sample_values"],
                                    },
                                )
                            if result and "error" not in result:
                                st.session_state["last_result"] = result
                                st.info(
                                    "Mapping ready — switch to **Map Variables** in the sidebar to review and submit a decision."
                                )


# ---------- Page: Feedback Dashboard ------------------------------------------

elif page == "Feedback Dashboard":
    st.markdown("### Feedback metrics")
    st.caption(
        "Aggregate review data. In a production system this is the signal source "
        "for retraining, retrieval reweighting, and the 25% accuracy improvement metric."
    )

    stats = api_get("/feedback/stats")
    if stats:
        cols = st.columns(5)
        labels = [
            ("Total reviews", stats.get("total_reviews", 0)),
            ("Accepted", stats.get("accepted", 0)),
            ("Edited", stats.get("edited", 0)),
            ("Rejected", stats.get("rejected", 0)),
            ("Acceptance rate", f"{stats.get('acceptance_rate', 0):.1%}"),
        ]
        for col, (label, value) in zip(cols, labels):
            with col:
                st.markdown(
                    f'<div class="stat-card"><div class="stat-label">{label}</div>'
                    f'<div class="stat-value">{value}</div></div>',
                    unsafe_allow_html=True,
                )

        st.markdown(
            f"<p class='small-muted'>Avg confidence of suggestions: <b>{stats.get('avg_suggested_confidence', 0):.2f}</b></p>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("### Recent decisions")

    feedback = api_get("/feedback")
    if feedback and feedback.get("feedback"):
        df = pd.DataFrame(feedback["feedback"])
        display_cols = [
            "timestamp", "raw_variable_name", "suggested_domain", "suggested_variable",
            "suggested_confidence", "decision", "final_domain", "final_variable",
            "reviewer_note",
        ]
        display_cols = [c for c in display_cols if c in df.columns]
        st.dataframe(df[display_cols], use_container_width=True, height=400)
    else:
        st.info("No feedback logged yet. Map a few variables to populate this view.")
