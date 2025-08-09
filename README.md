# AI PCS Code Generator (ICD-10-PCS, Section '0')

Deterministic, guideline-first PCS codes from uploaded procedure notes.

**Pipeline**
1. Upload note (.pdf/.md/.txt) → text extraction
2. (Optional) AI checklist detection (Gemini 2.0 Flash) — Debridement / Aneurysm Repair — or skip if out-of-scope
3. Apply 2025 guideline rules + checklist constraints
4. Index (3-char prefixes, Section '0') → Tables expansion (valid row combos)
5. Filters: Body Part Key (pos4), Approach (pos5), Device Key + Aggregation (pos6), Qualifier (pos7)
6. Output 7-character PCS codes with rationale

## Run locally
```bash
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

## Environment / Secrets
- Local: set `GEMINI_API_KEY` in your shell (see `.env.example`).
- Streamlit Cloud: set the key in **App → Settings → Secrets** (or `.streamlit/secrets.toml` while testing locally).  
  The app reads `st.secrets["GEMINI_API_KEY"]` first, then falls back to `os.environ["GEMINI_API_KEY"]`.

## Layout
```
app/
  streamlit_app.py
  modules/
    index_loader.py
    tables_loader.py
    guided_navigator.py
    rules_engine.py
    rules_registry.py
    ai_checklist.py
    checklist_loader.py
  components/
data/   # XML/JSON resources
docs/
scripts/
tests/
.streamlit/
  secrets.toml  # (ignored by git)
```

## Notes
- If Gemini key is not available or API fails, the classifier falls back to keywords. Code assembly remains deterministic using official tables.
