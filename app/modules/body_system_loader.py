import json
from pathlib import Path

def load_body_systems_section0(path: str | None = None):
    """Load Medical & Surgical (Section 0) Body System mapping JSON."""
    p = Path(path or Path(__file__).resolve().parents[1] / "data" / "medical_surgical_body_systems_2025.json")
    data = json.loads(p.read_text(encoding="utf-8"))
    # Basic shape checks
    if data.get("section") != "0":
        raise ValueError("Body system JSON section must be '0' for Medical & Surgical.")
    if "allowed_chars_in_section" not in data or "body_system_map" not in data:
        raise ValueError("Missing required keys in body system JSON.")
    return data