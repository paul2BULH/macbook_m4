import os, re, json
from typing import Dict, List, Tuple

CHECKLISTS = {
    "debridement": {
        "title": "Debridement",
        "keywords": [r"\bdebrid(e|)ment\b", r"\bI\s*&\s*D\b", r"\bincision and drainage\b",
                     r"\bexcisional debridement\b", r"\bnon[- ]excisional debridement\b"]
    },
    "aneurysm_repair": {
        "title": "Aneurysm Repair",
        "keywords": [r"\baneurysm\b", r"\bEVAR\b", r"\bendograft\b", r"\bstent graft\b",
                     r"\barch replacement\b", r"\bendoleak\b", r"\bcoil embolization\b"]
    }
}

def _keyword_score(text: str, patterns: List[str]) -> float:
    t = text.lower(); score = 0.0
    for pat in patterns:
        if re.search(pat, t, flags=re.IGNORECASE):
            score += 0.25
    return min(score, 0.95)

def classify_with_gemini(text: str, labels: List[str]) -> Dict[str, float]:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    try:
        import google.generativeai as genai  # type: ignore
        if not api_key: raise RuntimeError("No GEMINI_API_KEY in environment")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        sys_prompt = ("You are a multi-label classifier. Given a clinical procedure note, "
                      "return probabilities for each of these labels: " + ", ".join(labels) +
                      ". Only output JSON mapping label to probability (0..1) with keys exactly matching the labels.")
        prompt = sys_prompt + "\n\n=== NOTE TEXT START ===\n" + text + "\n=== NOTE TEXT END ==="
        resp = model.generate_content(prompt)
        content = resp.candidates[0].content.parts[0].text if resp and resp.candidates else "{}"
        data = json.loads(content)
        out = {k: float(max(0.0, min(1.0, v))) for k,v in data.items() if k in labels}
        if out: return out
    except Exception:
        pass
    return {lab: _keyword_score(text, CHECKLISTS[lab]["keywords"]) for lab in labels}

def detect_checklist(text: str) -> Tuple[str, float, Dict[str,float]]:
    labels = list(CHECKLISTS.keys())
    dist = classify_with_gemini(text, labels)
    dist = {k: float(v) for k,v in dist.items() if k in labels}
    if not dist: return "", 0.0, {}
    top = sorted(dist.items(), key=lambda x: x[1], reverse=True)
    top_label, top_score = top[0]
    second = top[1][1] if len(top) > 1 else 0.0
    if top_score >= 0.7 and (top_score - second) >= 0.15: return top_label, top_score, dist
    if top_score >= 0.5 and second < 0.5: return top_label, top_score, dist
    return "", top_score, dist
