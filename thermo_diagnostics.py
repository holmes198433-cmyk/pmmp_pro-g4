import math
from typing import Dict, List, Set, Any

class ThermodynamicDiagnosticEngine:
    """
    Evaluates thermodynamic models, fuel trim matrices, and
    traverses causal dependency graphs for root-cause isolation.
    """
    def __init__(self, displacement_liters: float = 2.0):
        self.displacement = displacement_liters
        self.R_spec = 0.28705  
        self._prev_idle_ltft = 0.0 
        
        self.dependency_graph: Dict[str, Set[str]] = {
            "P0101": {"P0171", "P0174", "P0300", "P0301", "P0302", "P0303", "P0304"},
            "P0102": {"P0171", "P0174", "P0300"},
            "P0171": {"P0300", "P0301", "P0302", "P0303", "P0304"},
            "P0507": {"P0171"}
        }

    def calculate_volumetric_efficiency(self, telemetry: Dict[str, Any]) -> float:
        maf = telemetry.get("MAF", 0.0)
        rpm = telemetry.get("RPM", 0.0)
        map_abs = telemetry.get("MAP", 101.3) 
        iat_c = telemetry.get("IAT", 25.0)
        
        if rpm < 200 or map_abs <= 0:
            return 0.0
            
        iat_k = iat_c + 273.15
        ve = (maf * iat_k * 120.0) / (self.displacement * rpm * map_abs) * self.R_spec
        return float(ve)

    def evaluate_fuel_trim_matrix(self, telemetry: Dict[str, Any]) -> List[str]:
        insights = []
        ltft = telemetry.get("LTFT", 0.0)
        rpm = telemetry.get("RPM", 0.0)
        load = telemetry.get("LOAD", 0.0)
        
        if 500 < rpm < 1000 and load < 25.0:
            self._prev_idle_ltft = ltft  
            if ltft > 10.0:
                insights.append("STATE_IDLE_LEAN: Positive fuel trim accumulation detected at idle.")
        
        if 2000 <= rpm <= 3000 and load >= 30.0:
            if ltft < 3.0 and self._prev_idle_ltft > 10.0:
                insights.append("ROOT_CAUSE_ISOLATED: Intake Vacuum Leak downstream of throttle plate.")
            elif ltft > 10.0 and self._prev_idle_ltft > 10.0:
                insights.append("ROOT_CAUSE_ISOLATED: Fuel Delivery Restriction (Weak Pump / Clogged Filter).")
                
        return insights

    def isolate_root_dtcs(self, active_dtcs: List[str]) -> Dict[str, Any]:
        active_set = set(active_dtcs)
        suppressed_codes = set()

        for parent, children in self.dependency_graph.items():
            if parent in active_set:
                suppressed_codes.update(children.intersection(active_set))

        unmasked_primaries = list(active_set - suppressed_codes)

        return {
            "root_causes": unmasked_primaries,
            "suppressed_symptom_codes": list(suppressed_codes),
            "raw_input_codes": active_dtcs
        }