from typing import Dict, Any

class LocalServiceManualRAG:
    """
    Retrieval-Augmented Generation interface querying local service manuals.
    """
    def __init__(self, manual_db_path: str = "./service_manuals"):
        self.db_path = manual_db_path
        self.document_store = {
            "P0101": {
                "target_component": "Mass Air Flow (MAF) Sensor",
                "pinout_specs": {"Pin 1 (12V Supply)": "12.0V +/- 0.5V", "Pin 2 (Ground)": "< 0.1V", "Pin 3 (Signal)": "1.1V - 1.3V @ 750 RPM"},
                "inspection_steps": ["Verify 12V power supply at harness.", "Check hot-wire sense element for dirt accumulation."],
                "schematic": "SCHEMATIC-ENG-P0101-REV3.pdf"
            },
            "P0171": {
                "target_component": "Fuel System / Intake Tract",
                "pinout_specs": {"O2 Sensor Heater": "12.0V", "Signal": "0.1V - 0.9V Oscillating"},
                "inspection_steps": ["Check for unmetered air leaks past MAF.", "Verify fuel pressure at rail."],
                "schematic": "SCHEMATIC-FUEL-SYS.pdf"
            }
        }

    def query_diagnostic_procedure(self, root_dtc: str) -> Dict[str, Any]:
        data = self.document_store.get(root_dtc, {
            "target_component": "Unknown Component",
            "pinout_specs": {},
            "inspection_steps": ["Refer to manufacturer specific OEM service manual."],
            "schematic": "N/A"
        })
        return {"code": root_dtc, **data}