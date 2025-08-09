from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Any
import json

from index_loader import PCSIndex
from tables_loader import PCSTables, TableRow, PCSTable
from rules_engine import RulesEngine

@dataclass
class GuidedCandidate:
    code7: str
    labels: Dict[str, str]
    rationale: List[str]

class DeviceResolver:
    def __init__(self, key_map: Dict[str, List[str]], agg_rows: List[Dict[str, Any]]):
        self.key_map = {k.lower(): v for k, v in key_map.items()}
        self.agg = agg_rows
    def normalize_terms(self, raw: Optional[str]) -> List[str]:
        if not raw: return []
        terms = [s.strip() for s in raw.split("/") if s.strip()]
        out = []
        for t in terms:
            tl = t.lower()
            if tl in self.key_map: out.extend(self.key_map[tl])
            else: out.append(t)
        seen = set(); final = []
        for x in out:
            if x not in seen:
                seen.add(x); final.append(x)
        return final
    def aggregate_for_table(self, device_value: str, operation_label: Optional[str], body_system_code: Optional[str]) -> List[str]:
        results = [device_value]
        op_l = (operation_label or "").lower()
        bs = body_system_code
        for row in self.agg:
            if row.get("device") != device_value: continue
            parents = [row.get("parent")] if isinstance(row.get("parent"), str) else (row.get("parent") or [])
            ops = row.get("operations") or []
            bsys = row.get("body_systems") or []
            op_ok = (not ops) or ("All applicable" in ops) or any((o or "").lower() in op_l for o in ops)
            bs_ok = (not bsys) or (bs is None) or (bs in bsys)
            if op_ok and bs_ok:
                for p in parents:
                    if p and p not in results:
                        results.append(p)
        return results

class BodyPartResolver:
    def __init__(self, key_map: Dict[str, List[str]]):
        self.key_map = {k.lower(): v for k, v in key_map.items()}
    def resolve_allowed_labels(self, anatomy_terms: List[str]) -> List[str]:
        allowed: List[str] = []
        for term in anatomy_terms or []:
            tl = (term or "").lower()
            if tl in self.key_map: allowed.extend(self.key_map[tl])
        seen = set(); out = []
        for a in allowed:
            al = a.lower()
            if al not in seen:
                seen.add(al); out.append(a)
        return out

class GuidedNavigator:
    def __init__(self, index_xml: str, tables_xml: str, rules_engine: RulesEngine,
                 device_key_json: Optional[str] = None, device_agg_json: Optional[str] = None,
                 body_part_key_json: Optional[str] = None):
        self.index = PCSIndex(index_xml)
        self.tables = PCSTables(tables_xml)
        self.rules_engine = rules_engine
        self.device_resolver: Optional[DeviceResolver] = None
        if device_key_json and device_agg_json:
            try:
                key_map = json.load(open(device_key_json, "r", encoding="utf-8"))
                agg_rows = json.load(open(device_agg_json, "r", encoding="utf-8"))
                if "data" in key_map: key_map = key_map["data"]
                if "data" in agg_rows: agg_rows = agg_rows["data"]
                self.device_resolver = DeviceResolver(key_map, agg_rows)
            except Exception:
                self.device_resolver = None
        self.body_part_resolver: Optional[BodyPartResolver] = None
        if body_part_key_json:
            try:
                bp_map = json.load(open(body_part_key_json, "r", encoding="utf-8"))
                if "data" in bp_map: bp_map = bp_map["data"]
                self.body_part_resolver = BodyPartResolver(bp_map)
            except Exception:
                self.body_part_resolver = None

    def _score_operation_against_hints(self, op_label: str, mutations: List[dict], checklist: dict = None) -> int:
        op = (op_label or "").lower(); score = 0
        for m in mutations:
            if "set" in m and m["set"].get("qualifier") == "Diagnostic":
                if any(k in op for k in ["excision","extraction","drainage"]): score += 10
        for m in mutations:
            if "set" in m and "root_operation_hint" in m["set"]:
                if m["set"]["root_operation_hint"].lower() in op: score += 8
        if checklist and checklist.get('root_op_priority'):
            for i, name in enumerate(checklist['root_op_priority']):
                if name and name.lower() in op:
                    score += max(5 - i, 1); break
        return score

    def _match_label(self, label: str, want: Optional[str]) -> bool:
        if not want: return True
        if not label: return False
        return want.lower() in label.lower()

    def _pos4_keep(self, l4: str, facts: Dict[str, Any]) -> Tuple[bool, str]:
        cl = facts.get('checklist') if isinstance(facts, dict) else None
        if cl and cl.get('allowed_pos4_labels'):
            allowed = [a.lower() for a in cl['allowed_pos4_labels']]
            if (l4 or '').lower() not in allowed:
                return False, 'Body part restricted by checklist'
        if not self.body_part_resolver: return True, ""
        anatomy_terms = facts.get("anatomy_terms") or []
        if not anatomy_terms:
            iq = facts.get("index_query")
            if iq: anatomy_terms = [iq]
        allowed = [a.lower() for a in self.body_part_resolver.resolve_allowed_labels(anatomy_terms)]
        if not allowed: return True, ""
        l4l = (l4 or "").lower()
        for a in allowed:
            if a in l4l: return True, f"Body part matched via key: {anatomy_terms} → {a}"
        return False, "Body part not in key-mapped set"

    def _device_label_match(self, table: PCSTable, row: TableRow, l6: str, want_device_raw: Optional[str], muts: List[dict]) -> Tuple[bool, str]:
        for m in muts:
            if "set" in m and m["set"].get("device", "").lower() == "no device":
                return ("no device" in (l6 or "").lower(), "Device forced to 'No Device' by rule")
        if not want_device_raw: return (True, "")
        if not self.device_resolver:
            return (self._match_label(l6, want_device_raw), f"Simple device match to '{want_device_raw}' (no resolver)")
        specifics = self.device_resolver.normalize_terms(want_device_raw)
        allowed_labels = set()
        for spec in specifics:
            for lab in self.device_resolver.aggregate_for_table(spec, table.operation_label, table.body_system):
                allowed_labels.add(lab.lower())
        l6l = (l6 or "").lower()
        for lab in allowed_labels:
            if lab in l6l:
                return (True, f"Device matched via key/aggregation: '{want_device_raw}' → {list(allowed_labels)}")
        return (False, f"Device '{want_device_raw}' not compatible with this table row")

    def propose_codes(self, query: str, facts: Dict[str, any], limit: int = 25) -> Dict[str, any]:
        outcome = self.rules_engine.apply(facts, tables_context=None)
        muts = outcome.mutations

        hits = self.index.lookup(query, max_results=60)
        prefixes = []; seen = set()
        for h in hits:
            for p in h.code_prefixes:
                if len(p) >= 3 and p[0] == '0':
                    pref = p[:3]
                    if pref not in seen: seen.add(pref); prefixes.append(pref)

        scored = []
        for pref in prefixes:
            expansions = self.tables.expand_from_prefix(pref)
            if not expansions: continue
            table, _ = expansions[0]
            s = self._score_operation_against_hints(table.operation_label, muts, facts.get('checklist') if isinstance(facts, dict) else None)
            scored.append((s, pref, table.operation_label))
        scored.sort(reverse=True)

        want_approach = facts.get("approach_name")
        want_device = facts.get("device_name")
        for m in muts:
            if "set" in m and "device" in m["set"]:
                want_device = m["set"]["device"]
        want_qual = None
        for m in muts:
            if "set" in m and "qualifier" in m["set"]:
                want_qual = m["set"]["qualifier"]

        guided: List[GuidedCandidate] = []
        for _, pref, op_label in scored[:10]:
            for table, row in self.tables.expand_from_prefix(pref):
                for c4, l4 in row.pos4.labels.items():
                    keep4, why4 = self._pos4_keep(l4, facts)
                    if not keep4: continue
                    for c5, l5 in row.pos5.labels.items():
                        cl = facts.get('checklist') if isinstance(facts, dict) else None
                        req_appr = cl.get('approach_required') if cl else None
                        if req_appr and not self._match_label(l5, req_appr): continue
                        if not self._match_label(l5, want_approach): continue
                        for c6, l6 in row.pos6.labels.items():
                            keep6, why6 = self._device_label_match(table, row, l6, want_device, muts)
                            if not keep6: continue
                            for c7, l7 in row.pos7.labels.items():
                                if want_qual and not self._match_label(l7, want_qual): continue
                                code = pref + c4 + c5 + c6 + c7
                                rationale = []
                                if why4: rationale.append(why4)
                                if want_qual: rationale.append(f"Qualifier matched '{want_qual}'")
                                if want_approach: rationale.append(f"Approach matched '{want_approach}'")
                                if why6: rationale.append(why6)
                                rationale.append(f"Operation prioritized as '{op_label}'")
                                guided.append(GuidedCandidate(code7=code, labels={
                                    "pos4": l4, "pos5": l5, "pos6": l6, "pos7": l7, "operation": op_label
                                }, rationale=rationale))
                                if len(guided) >= limit:
                                    return {"prefixes_considered": [p for _, p, _ in scored[:10]],
                                            "candidates": [g.__dict__ for g in guided],
                                            "mutations": muts, "actions": outcome.actions}
        return {"prefixes_considered": [p for _, p, _ in scored[:10]],
                "candidates": [g.__dict__ for g in guided],
                "mutations": muts, "actions": outcome.actions}
