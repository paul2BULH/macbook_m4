from __future__ import annotations
from dataclasses import dataclass
from typing import List
import xml.etree.ElementTree as ET
import re

@dataclass
class IndexHit:
    term_path: List[str]
    kind: str
    value: str
    code_prefixes: List[str]

class PCSIndex:
    def __init__(self, xml_path: str):
        self.root = ET.parse(xml_path).getroot()

    def _extract_codes(self, text: str) -> List[str]:
        if not text: return []
        return re.findall(r"[0-9A-Z]{3,7}", text.upper())

    def _walk(self, node: ET.Element, path: List[str]) -> List[IndexHit]:
        hits: List[IndexHit] = []
        for tag in ["code", "codes", "tab", "see", "use"]:
            for child in node.findall(tag):
                val = (child.text or "").strip()
                hits.append(IndexHit(term_path=path[:], kind=tag, value=val, code_prefixes=self._extract_codes(val)))
        for term in node.findall("term"):
            ttitle = (term.findtext("title") or "").strip()
            hits.extend(self._walk(term, path + ([ttitle] if ttitle else [])))
        return hits

    def lookup(self, query: str, max_results: int = 50) -> List[IndexHit]:
        q = (query or "").strip().lower()
        if not q: return []
        results: List[IndexHit] = []
        for letter in self.root.findall("letter"):
            for main in letter.findall("mainTerm"):
                mt = (main.findtext("title") or "").strip()
                path0 = [mt] if mt else []
                if mt and q in mt.lower():
                    results.extend(self._walk(main, path0))
                for term in main.findall(".//term"):
                    ttitle = (term.findtext("title") or "").strip()
                    if ttitle and q in ttitle.lower():
                        results.extend(self._walk(term, path0 + [ttitle]))
        uniq = []
        seen = set()
        for h in results:
            key = (tuple(h.term_path), h.kind, h.value)
            if key not in seen:
                seen.add(key); uniq.append(h)
        return uniq[:max_results]
