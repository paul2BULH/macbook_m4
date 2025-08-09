import xml.etree.ElementTree as ET
_STATE = {"defs": None}
def init(defs_xml_path: str) -> None:
    try:
        _STATE["defs"] = ET.parse(defs_xml_path).getroot()
    except Exception:
        _STATE["defs"] = None
