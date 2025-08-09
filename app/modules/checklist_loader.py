import json, os
from typing import Dict, Any

def load_debridement_constraints(path: str) -> Dict[str, Any]:
    data = json.load(open(path, "r", encoding="utf-8"))
    ref = data.get("debridement_procedure_coding_reference", {})
    root_op_priority = ["Excision", "Extraction", "Drainage"]
    allowed_pos4 = []
    bp = ref.get("character_4_body_part") or {}
    if isinstance(bp, dict):
        vals = bp.get("body_part_values")
        if isinstance(vals, dict):
            for code,label in vals.items():
                if isinstance(label, str):
                    allowed_pos4.append(label)
    return {"root_op_priority": root_op_priority, "allowed_pos4_labels": allowed_pos4 or None,
            "approach_required": None, "device_hint": None, "qualifier_hint": None}

def load_aneurysm_constraints(path: str) -> Dict[str, Any]:
    data = json.load(open(path, "r", encoding="utf-8"))
    ref = data.get("aneurysm_repair_coding_reference", {})
    root_op_priority, approach_required, device_hint = [], None, None
    procs = ref.get("procedures") or {}
    if isinstance(procs, dict):
        for name, obj in procs.items():
            ro = obj.get("root_operation")
            if isinstance(ro, str) and ro not in root_op_priority:
                root_op_priority.append(ro)
            appr = obj.get("approach", {}).get("primary")
            if appr and not approach_required:
                approach_required = appr
            dev = obj.get("device", {})
            if isinstance(dev, dict) and isinstance(dev.get("options"), list) and dev["options"]:
                ex = dev["options"][0]
                if isinstance(ex, dict) and "type" in ex:
                    device_hint = ex["type"]
    if not root_op_priority:
        root_op_priority = ["Occlusion", "Restriction", "Replacement", "Bypass", "Supplement", "Insertion"]
    return {"root_op_priority": root_op_priority, "allowed_pos4_labels": None,
            "approach_required": approach_required, "device_hint": device_hint, "qualifier_hint": None}

def load_constraints(checklist_id: str) -> Dict[str, Any]:
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
    if checklist_id == "debridement":
        return load_debridement_constraints(os.path.join(data_dir, "debridement_coding_json.json"))
    if checklist_id == "aneurysm_repair":
        return load_aneurysm_constraints(os.path.join(data_dir, "aneurysm_repair_json.json"))
    return {}
