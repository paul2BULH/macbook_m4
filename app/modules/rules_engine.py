from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class RuleOutcome:
    mutations: List[Dict[str,Any]]
    actions: List[str]

def _lower(val):
    try:
        return (val or "").lower()
    except Exception:
        return ""

class RulesEngine:
    def __init__(self, rules: Dict[str,Any] | List[Dict[str,Any]]):
        self.rules = rules

    def apply(self, facts: Dict[str,Any], tables_context=None) -> RuleOutcome:
        muts: List[Dict[str,Any]] = []
        actions: List[str] = []

        flags = set((facts or {}).get("raw_text_flags") or [])

        if "biopsy" in flags:
            muts.append({"set": {"qualifier": "Diagnostic"}})

        device_name_l = _lower((facts or {}).get("device_name"))
        if "removed at end" in flags or device_name_l == "no device":
            muts.append({"set": {"device": "No Device"}})

        if isinstance(facts, dict) and facts.get("checklist"):
            co = facts["checklist"]
            if isinstance(co, dict) and co.get("root_op_priority"):
                muts.append({"note": {"root_op_priority": co["root_op_priority"]}})

        return RuleOutcome(mutations=muts, actions=actions)
