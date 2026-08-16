import os
import re
from typing import Any, Dict, List, Optional


class LocalServiceManualRAG:
    """
    Local vector/text retrieval engine for OEM service manuals and diagnostic procedures.
    Indexes .txt and .md manual files under the manuals directory.
    """

    HEADERS = {"User-Agent": "Mozilla/5.0"}

    def __init__(self, manuals_dir: str = "manuals", db_path: str = "./service_manuals_index.json"):
        self.manuals_dir = manuals_dir
        self.db_path = db_path
        self.headers = dict(self.HEADERS)
        os.makedirs(self.manuals_dir, exist_ok=True)

        self.document_store = {
            "P0101": {
                "target_component": "Mass Air Flow (MAF) Sensor",
                "pinout_specs": {
                    "Pin 1 (12V Supply)": "12.0V +/- 0.5V",
                    "Pin 2 (Ground)": "< 0.1V",
                    "Pin 3 (Signal)": "1.1V - 1.3V @ 750 RPM",
                },
                "inspection_steps": [
                    "Verify 12V power supply at harness.",
                    "Check hot-wire sense element for dirt accumulation.",
                ],
                "schematic": "SCHEMATIC-ENG-P0101-REV3.pdf",
            },
            "P0171": {
                "target_component": "Fuel System / Intake Tract",
                "pinout_specs": {
                    "O2 Sensor Heater": "12.0V",
                    "Signal": "0.1V - 0.9V Oscillating",
                },
                "inspection_steps": [
                    "Check for unmetered air leaks past MAF.",
                    "Verify fuel pressure at rail.",
                ],
                "schematic": "SCHEMATIC-FUEL-SYS.pdf",
            },
        }

    def _read_manual_files(self) -> List[Dict[str, str]]:
        documents = []
        if not os.path.isdir(self.manuals_dir):
            return documents

        for root, _, files in os.walk(self.manuals_dir):
            for file in files:
                if file.endswith((".txt", ".md")):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read().strip()
                            if content:
                                documents.append({"filename": file, "path": file_path, "content": content})
                    except Exception:
                        continue
        return documents

    def search_manuals(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Search indexed manuals for matching snippet passages with relevance scoring.
        """
        if not query or not query.strip():
            return []

        query_terms = [re.escape(w.lower()) for w in re.split(r"\s+", query.strip()) if w]
        if not query_terms:
            return []

        documents = self._read_manual_files()
        if not documents:
            return []

        passages = []
        for doc in documents:
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", doc["content"]) if p.strip()]
            for para in paragraphs:
                para_lower = para.lower()
                matches = sum(len(re.findall(term, para_lower)) for term in query_terms)
                unique_matches = sum(1 for term in query_terms if re.search(term, para_lower))
                if matches > 0:
                    score = float(unique_matches * 2.0 + matches)
                    passages.append({
                        "passage": para,
                        "source": doc["filename"],
                        "score": round(score, 2),
                    })

        passages.sort(key=lambda x: x["score"], reverse=True)
        return passages[:limit]

    def get_pinout(self, connector_id: str, pin_number: str) -> Dict[str, Any]:
        """
        Parse indexed manual text for connector pinout tables matching the connector and pin.
        Returns pin_number, wire_color, circuit_name, and expected_voltage.
        """
        clean_conn = str(connector_id).strip() if connector_id else ""
        clean_pin = str(pin_number).strip() if pin_number else ""

        fallback = {
            "connector_id": clean_conn,
            "pin_number": clean_pin,
            "wire_color": "UNKNOWN",
            "circuit_name": "UNKNOWN",
            "expected_voltage": "UNKNOWN",
        }

        documents = self._read_manual_files()
        for doc in documents:
            content = doc["content"]
            if clean_conn and clean_conn.lower() not in content.lower():
                continue

            for line in content.splitlines():
                # Markdown table row format: | pin | wire_color | circuit_name | expected_voltage |
                table_match = re.match(
                    r"^\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*$",
                    line,
                )
                if table_match:
                    pin, wire_color, circuit, voltage = [g.strip() for g in table_match.groups()]
                    if pin.lower() == clean_pin.lower() or pin.lstrip("0") == clean_pin.lstrip("0"):
                        return {
                            "connector_id": clean_conn,
                            "pin_number": clean_pin,
                            "wire_color": wire_color,
                            "circuit_name": circuit,
                            "expected_voltage": voltage,
                        }

                # Key-value / delimited format
                kv_match = re.search(
                    r"(?:pin\s*)?"
                    + re.escape(clean_pin)
                    + r"\b.*?color[:=]\s*([A-Za-z/]+).*?circuit[:=]\s*([^,;\n]+).*?voltage[:=]\s*([^,;\n]+)",
                    line,
                    re.IGNORECASE,
                )
                if kv_match:
                    wire_color, circuit, voltage = [g.strip() for g in kv_match.groups()]
                    return {
                        "connector_id": clean_conn,
                        "pin_number": clean_pin,
                        "wire_color": wire_color,
                        "circuit_name": circuit,
                        "expected_voltage": voltage,
                    }

        # Fallback to document store pinout specs if available
        for dtc_data in self.document_store.values():
            specs = dtc_data.get("pinout_specs", {})
            for key, val in specs.items():
                if f"Pin {clean_pin}" in key or f"Pin {clean_pin.lstrip('0')}" in key:
                    circuit_name = key
                    match_paren = re.search(r"\((.*?)\)", key)
                    if match_paren:
                        circuit_name = match_paren.group(1)
                    return {
                        "connector_id": clean_conn,
                        "pin_number": clean_pin,
                        "wire_color": "UNKNOWN",
                        "circuit_name": circuit_name,
                        "expected_voltage": val,
                    }

        return fallback

    def query_diagnostic_procedure(self, root_dtc: str) -> Dict[str, Any]:
        """Queries local documentation store for relevant repair data."""
        clean_dtc = root_dtc.strip().upper() if root_dtc else ""
        data = self.document_store.get(
            clean_dtc,
            {
                "target_component": "Unknown Component",
                "pinout_specs": {},
                "inspection_steps": [
                    "Refer to manufacturer specific OEM service manual for routing and pinpoint tests."
                ],
                "schematic": "N/A",
            },
        )
        return {"code": clean_dtc, **data}
