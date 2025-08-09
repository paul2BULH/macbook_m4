import os, sys, io, re, json
import streamlit as st

if "GEMINI_API_KEY" in st.secrets:
    os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]

APP_DIR = os.path.dirname(__file__)
MOD_DIR = os.path.join(APP_DIR, "modules")
DATA_DIR = os.path.join(os.path.dirname(APP_DIR), "data")
if MOD_DIR not in sys.path:
    sys.path.append(MOD_DIR)

from rules_registry import init as defs_init
from rules_engine import RulesEngine
from guided_navigator import GuidedNavigator
from ai_checklist import detect_checklist, CHECKLISTS
from checklist_loader import load_constraints

DEFS_XML   = os.path.join(DATA_DIR, "icd10pcs_definitions_2025.xml")
INDEX_XML  = os.path.join(DATA_DIR, "icd10pcs_index_2025.xml")
TABLES_XML = os.path.join(DATA_DIR, "icd10pcs_tables_2025.xml")
RULES_JSON = os.path.join(DATA_DIR, "pcs_guidelines_rules_2025.json")
BP_KEY     = os.path.join(DATA_DIR, "body_part_key.json")
DV_KEY     = os.path.join(DATA_DIR, "device_key.json")
DV_AGG     = os.path.join(DATA_DIR, "device_aggregation.json")

st.set_page_config(page_title="AI PCS Code Generator", layout="wide")
st.title("AI PCS Code Generator — Chart → Codes (Section '0')")

if 'init_done' not in st.session_state:
    defs_init(DEFS_XML)
    st.session_state['rules'] = json.load(open(RULES_JSON, "r", encoding="utf-8"))
    st.session_state['engine'] = RulesEngine(st.session_state['rules'])
    st.session_state['nav'] = GuidedNavigator(INDEX_XML, TABLES_XML, st.session_state['engine'],
                                              device_key_json=DV_KEY, device_agg_json=DV_AGG,
                                              body_part_key_json=BP_KEY)
    st.session_state['init_done'] = True

with st.sidebar:
    st.subheader("Resources Loaded")
    for p in [DEFS_XML, INDEX_XML, TABLES_XML, RULES_JSON, BP_KEY, DV_KEY, DV_AGG]:
        st.caption(p)

def extract_text(file) -> str:
    data = file.read(); name = file.name.lower()
    if name.endswith((".txt",".md")):
        try: return data.decode("utf-8", errors="ignore")
        except Exception: return data.decode("latin-1", errors="ignore")
    if name.endswith(".pdf"):
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(data))
            return "\n".join([(p.extract_text() or "") for p in reader.pages])
        except Exception:
            st.error("PDF extract failed. Try .txt/.md or ensure PyPDF2 is installed."); return ""
    try: return data.decode("utf-8", errors="ignore")
    except Exception: return ""


def auto_facts(text: str) -> dict:
    t = (text or "").lower()
    flags = []
    if "biopsy" in t: flags.append("biopsy")
    if "drain left in place" in t or "jp drain" in t: flags.append("drain left in place")
    if "removed at end" in t or "no device left" in t: flags.append("removed at end")

    # Approach
    approach = None
    for rx, label in [
        (r"\bpercutaneous endoscopic\b", "Percutaneous Endoscopic"),
        (r"\bpercutaneous\b", "Percutaneous"),
        (r"via natural or artificial opening with percutaneous endoscopic assistance", "Via Natural or Artificial Opening With Percutaneous Endoscopic Assistance"),
        (r"via natural or artificial opening endoscopic", "Via Natural or Artificial Opening Endoscopic"),
        (r"\bvia natural or artificial opening\b", "Via Natural or Artificial Opening"),
        (r"\bopen\b", "Open"),
        (r"\bexternal\b", "External"),
    ]:
        if re.search(rx, t): approach = label; break

    # Device
    device = None
    if "no device left" in t or "removed at end" in t:
        device = "No Device"
    elif "stent" in t or "implant" in t or "catheter" in t:
        device = "Stent"

    # Strong terms
    strong_terms = [
        ("excisional debridement", "debridement"),
        ("irrigation and debridement", "debridement"),
        ("incision & drainage", "incision and drainage"),
        ("incision and drainage", "incision and drainage"),
        ("i & d", "incision and drainage"),
        ("biopsy", "biopsy"),
        ("excision", "excision"),
        ("resection", "resection"),
        ("debridement", "debridement"),
    ]
    query = None
    for needle, q in strong_terms:
        if needle in t:
            query = q; break

    anatomy_terms = []
    for organ in ["groin","thigh","skin","subcutaneous","soft tissue","arm","leg","hand","foot","abdomen","chest","back"]:
        if organ in t: anatomy_terms.append(organ)

    if not query:
        m = re.search(r"\b([a-z]{5,})\b", t)
        query = m.group(1) if m else "procedure"

    return {"raw_text_flags": flags, "approach_name": approach, "device_name": device,
            "index_query": query, "anatomy_terms": anatomy_terms}



st.markdown("### Upload Procedure Note (.pdf, .md, .txt)")
uploaded = st.file_uploader("Upload", type=["pdf","md","txt"])

st.markdown("### Checklist (Auto-Detect)")
use_ai = st.checkbox("Auto-select checklist (AI)", value=True)

facts = {}; text_preview = ""; constraints = {}

if uploaded:
    text_preview = extract_text(uploaded)
    if text_preview:
        facts = auto_facts(text_preview)
        with st.expander("Extracted Text (preview)"):
            st.text(text_preview[:4000])
        st.success(f"Auto facts: {facts}")
        selected_checklist = ""
        from ai_checklist import detect_checklist, CHECKLISTS
        label, conf, dist = detect_checklist(text_preview) if use_ai else ("", 0.0, {})
        if use_ai and label:
            selected_checklist = label
            st.info(f"Checklist auto-selected: {CHECKLISTS[label]['title']} (confidence {conf:.2f})")
        elif use_ai and not label and dist:
            st.warning("Checklist ambiguous — please select one:")
            options = [k for k,_ in sorted(dist.items(), key=lambda x: x[1], reverse=True)]
            titles = {k: CHECKLISTS[k]['title'] for k in options}
            pick = st.radio("Select checklist", options=options, format_func=lambda k: f"{titles[k]} ({dist[k]:.2f})")
            selected_checklist = pick
        if selected_checklist:
            from checklist_loader import load_constraints
            constraints = load_constraints(selected_checklist)
            st.caption(f"Checklist constraints loaded: {selected_checklist}")

st.markdown("### Optional Overrides")
c1, c2, c3 = st.columns(3)
with c1:
    approach_in = st.text_input("Approach", value=(facts.get("approach_name") or ""))
with c2:
    device_in = st.text_input("Device", value=(facts.get("device_name") or ""))
with c3:
    flags_in = st.text_input("Flags", value=", ".join(facts.get("raw_text_flags", [])))
query_default = facts.get("index_query","")
# If AI picked a checklist and the query looks generic, steer to checklist title
if constraints and (query_default in ("procedure","operative","operation","surgery")):
    # Use a label that will resolve in index
    if "debridement" in (constraints.get("root_op_priority") or []) or True:
        query_default = "debridement"
query_in = st.text_input("Index Term", value=query_default)

if st.button("Analyze & Propose PCS Codes", type="primary"):
    if not text_preview:
        st.warning("Please upload a note first.")
    else:
        flags = [x.strip() for x in re.split(r"[\n,;]+", flags_in) if x.strip()]
        query = query_in or facts.get("index_query") or "procedure"
        full_facts = {
            "raw_text_flags": flags,
            "anatomy_terms": [query] if query else [],
            "checklist": constraints or {},
            "approach_name": approach_in or None,
            "device_name": device_in or None
        }
        nav = st.session_state['nav']
        res = nav.propose_codes(query, full_facts, limit=50)
        st.caption(f"Prefixes considered: {', '.join(res.get('prefixes_considered', []))}")
        cands = res.get("candidates", [])
        if not cands:
            st.warning("No candidates after filtering.")
        else:
            import pandas as pd
            rows = [{
                "PCS Code": c["code7"],
                "Operation": c["labels"].get("operation",""),
                "Body Part (pos4)": c["labels"].get("pos4",""),
                "Approach (pos5)": c["labels"].get("pos5",""),
                "Device (pos6)": c["labels"].get("pos6",""),
                "Qualifier (pos7)": c["labels"].get("pos7",""),
                "Rationale": " | ".join(c["rationale"]),
            } for c in cands]
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        with st.expander("Guideline Effects"):
            st.json({"mutations": res.get("mutations", []), "actions": res.get("actions", [])})
else:
    st.info("Upload a chart and click Analyze.")
