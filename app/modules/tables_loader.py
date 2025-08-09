from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import xml.etree.ElementTree as ET

@dataclass
class AxisLabels:
    title: str
    labels: Dict[str, str]

@dataclass
class TableRow:
    pos4: AxisLabels
    pos5: AxisLabels
    pos6: AxisLabels
    pos7: AxisLabels

@dataclass
class PCSTable:
    section: str
    body_system: str
    operation_code: str
    operation_label: str
    rows: List[TableRow]

class PCSTables:
    def __init__(self, xml_path: str):
        root = ET.parse(xml_path).getroot()
        self.tables: Dict[Tuple[str,str,str], PCSTable] = {}
        for t in root.findall("pcsTable"):
            ax1 = t.find(".//axis[@pos='1']/label")
            ax2 = t.find(".//axis[@pos='2']/label")
            ax3 = t.find(".//axis[@pos='3']/label")
            if ax1 is None or ax2 is None or ax3 is None:
                continue
            pos1, pos2, pos3 = ax1.get("code"), ax2.get("code"), ax3.get("code")
            pos3_label = (ax3.text or "").strip()
            rows: List[TableRow] = []
            for row in t.findall("pcsRow"):
                def read_axis(pos: str) -> AxisLabels:
                    a = row.find(f".//axis[@pos='{pos}']")
                    labels = {}
                    title = ""
                    if a is not None:
                        title = (a.findtext("title") or "").strip()
                        for lab in a.findall("label"):
                            labels[lab.get("code")] = (lab.text or "").strip()
                    return AxisLabels(title=title, labels=labels)
                rows.append(TableRow(read_axis("4"), read_axis("5"), read_axis("6"), read_axis("7")))
            self.tables[(pos1,pos2,pos3)] = PCSTable(pos1,pos2,pos3,pos3_label,rows)

    def get_table(self, pos1: str, pos2: str, pos3: str) -> Optional[PCSTable]:
        return self.tables.get((pos1,pos2,pos3))

    def expand_from_prefix(self, prefix: str):
        if len(prefix) < 3: return []
        key = (prefix[0], prefix[1], prefix[2])
        table = self.get_table(*key)
        if not table: return []
        return [(table, row) for row in table.rows]
