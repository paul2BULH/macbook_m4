from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class RuleOutcome:
    mutations: List[Dict[str,Any]]
    actions: List[str]

class RulesEngine:
    def __init__(self, rules: Dict[str,Any] | List[Dict[str,Any]]):
        self.rules = rules

    def apply(self, facts: Dict[str,Any], tables_context=None) -> RuleOutcome:
        muts: List[Dict[str,Any]] = []
        actions: List[str] = []
        flags = set((facts or {}).get("raw_text_flags") or [])

        if "biopsy" in flags:
            muts.append({"set": {"qualifier": "Diagnostic"}})

        if "removed at end" in flags or (facts or {}).get("device_name","").lower() == "no device":
            muts.append({"set": {"device": "No Device"}})

        if facts.get("checklist"):
            co = facts["checklist"]
            if co.get("root_op_priority"):
                muts.append({"note": {"root_op_priority": co["root_op_priority"]}})

        return RuleOutcome(mutations=muts, actions=actions)
