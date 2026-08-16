import csv
import os
from typing import Any, Dict, Optional


class DTCLoader:
    """
    Loads, parses, and provides lookups for OBD-II Diagnostic Trouble Codes.
    """

    PREFIX_SYSTEM_MAP = {
        "P": "Powertrain",
        "C": "Chassis",
        "B": "Body",
        "U": "Network",
    }

    def __init__(self, csv_path: Optional[str] = None):
        if csv_path is None:
            csv_path = os.path.join(os.path.dirname(__file__), "data", "dtc_codes.csv")
        self.csv_path = csv_path
        self._dtc_database: Dict[str, Dict[str, Any]] = {}
        self._load_dtc_database()

    def _load_dtc_database(self) -> None:
        if not os.path.isfile(self.csv_path):
            return

        with open(self.csv_path, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                code = row["code"].strip().upper()
                self._dtc_database[code] = {
                    "code": code,
                    "description": row.get("description", "").strip(),
                    "severity": row.get("severity", "WARNING").strip().upper(),
                    "system": row.get("system", "").strip(),
                }

    def lookup_code(self, code: str) -> Optional[Dict[str, Any]]:
        """
        Looks up DTC metadata in the loaded database.
        Returns code metadata if found, or generated fallback data based on code prefix.
        """
        if not code or not isinstance(code, str):
            return None

        normalized_code = code.strip().upper()
        if normalized_code in self._dtc_database:
            return self._dtc_database[normalized_code].copy()

        # Fallback categorization based on prefix
        prefix = normalized_code[0] if normalized_code else ""
        system = self.PREFIX_SYSTEM_MAP.get(prefix, "Unknown")
        severity = self.classify_severity(normalized_code)

        return {
            "code": normalized_code,
            "description": f"Unknown {system} Diagnostic Trouble Code ({normalized_code})",
            "severity": severity,
            "system": system,
        }

    def classify_severity(self, code: str) -> str:
        """
        Returns 'CRITICAL', 'WARNING', or 'INFORMATIONAL' severity for the given DTC.
        """
        if not code or not isinstance(code, str):
            return "INFORMATIONAL"

        normalized_code = code.strip().upper()
        if normalized_code in self._dtc_database:
            return self._dtc_database[normalized_code]["severity"]

        # Default fallback rules
        prefix = normalized_code[0] if normalized_code else ""
        if prefix in ("P", "C", "U"):
            return "WARNING"
        return "INFORMATIONAL"
