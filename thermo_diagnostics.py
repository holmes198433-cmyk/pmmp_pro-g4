import time
import math
from collections import deque
from typing import Dict, List, Set, Any, Optional, Tuple


class ThermodynamicDiagnosticEngine:
    """
    Evaluates thermodynamic models, O2 kinetics, 3x3 fuel trim matrices,
    volumetric breathing obstructions, and traverses causal dependency graphs.
    """

    def __init__(self, displacement_liters: float = 2.0, expected_wot_ve: float = 0.85):
        self.displacement = displacement_liters
        self.expected_wot_ve = expected_wot_ve
        self.R_spec = 0.28705
        self.baro_kpa_default = 101.3

        self._o2_history: deque = deque()
        self._last_o2_state_high: Optional[bool] = None
        self._o2_switch_timestamps: deque = deque()
        self.latest_o2_frequency_hz: float = 0.0

        self.fuel_trim_matrix: Dict[str, Dict[str, Optional[float]]] = {
            "RPM_LOW": {"LOAD_LOW": None, "LOAD_MID": None, "LOAD_HIGH": None},
            "RPM_MID": {"LOAD_LOW": None, "LOAD_MID": None, "LOAD_HIGH": None},
            "RPM_HIGH": {"LOAD_LOW": None, "LOAD_MID": None, "LOAD_HIGH": None},
        }

        self.dependency_graph: Dict[str, Set[str]] = {
            "P0100": {"P0171", "P0174", "P0300", "P0301", "P0302", "P0303", "P0304"},
            "P0101": {"P0171", "P0174", "P0300", "P0301", "P0302", "P0303", "P0304", "P0305", "P0306", "P0308"},
            "P0102": {"P0171", "P0174", "P0300", "P0301", "P0302", "P0303", "P0304"},
            "P0103": {"P0171", "P0174", "P0300"},
            "P0130": {"P0171", "P0174", "P0300"},
            "P0131": {"P0171", "P0300"},
            "P0133": {"P0171", "P0300"},
            "P0134": {"P0171", "P0300"},
            "P0087": {"P0171", "P0174", "P0300", "P0301", "P0302", "P0303", "P0304"},
            "P0089": {"P0171", "P0174", "P0300"},
            "P0505": {"P0171", "P0174"},
            "P0507": {"P0171", "P0174"},
            "P0171": {"P0300", "P0301", "P0302", "P0303", "P0304", "P0305", "P0306", "P0308"},
            "P0174": {"P0300", "P0301", "P0302", "P0303", "P0304", "P0305", "P0306", "P0308"},
            "P0300": {"P0301", "P0302", "P0303", "P0304", "P0305", "P0306", "P0308"},
            "P0420": {"P0136", "P0137", "P0138", "P0140"},
            "P0430": {"P0156", "P0157", "P0158", "P0160"},
        }

    def classify_operating_state(self, telemetry: Dict[str, Any]) -> str:
        """Classify the current operating state using RPM, load, and coolant temperature."""
        rpm = float(telemetry.get("RPM", 0) or 0)
        load = float(telemetry.get("LOAD", 0) or 0)
        coolant = float(telemetry.get("COOLANT", 0) or 0)

        if coolant < 70:
            return "cold_start"
        if rpm < 1000 and load < 25:
            return "idle"
        if rpm < 3500 and load < 70:
            return "cruise"
        if load > 65 or rpm > 3500:
            return "high_load"
        return "transient"

    def calculate_volumetric_efficiency(self, telemetry: Dict[str, Any]) -> float:
        """Calculates real-time engine Volumetric Efficiency (VE) using the Ideal Gas Law."""
        maf = telemetry.get("MAF", 0.0)
        rpm = telemetry.get("RPM", 0.0)
        map_abs = telemetry.get("MAP", 101.3)
        iat_c = telemetry.get("IAT", 25.0)

        if rpm < 200 or map_abs <= 0:
            return 0.0

        iat_k = iat_c + 273.15
        ve = (maf * iat_k * 120.0) / (self.displacement * rpm * map_abs) * self.R_spec
        return float(ve)

    def evaluate_residuals(self, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare measured values against expected ranges for the current operating state.
        This produces explanation-friendly residuals instead of raw threshold-only signals.
        """
        state = self.classify_operating_state(telemetry)
        residuals: Dict[str, Any] = {"state": state, "checks": []}

        rpm = float(telemetry.get("RPM", 0) or 0)
        load = float(telemetry.get("LOAD", 0) or 0)
        maf = float(telemetry.get("MAF", 0) or 0)
        stft = float(telemetry.get("STFT", 0) or 0)
        ltft = float(telemetry.get("LTFT", 0) or 0)
        o2_v = float(telemetry.get("O2_V", 0) or 0)

        if state in {"idle", "cruise"}:
            if stft > 10 or ltft > 10:
                residuals["checks"].append({
                    "name": "fuel_trim_lean_bias",
                    "value": stft + ltft,
                    "status": "lean_bias_detected",
                })

        if state in {"idle", "cruise"}:
            expected_maf = max(1.0, (rpm * 0.0035) + (load * 0.08))
            if maf < expected_maf * 0.75:
                residuals["checks"].append({
                    "name": "maf_low_for_state",
                    "value": maf,
                    "expected": expected_maf,
                    "status": "low_maf",
                })

        if o2_v > 0.7 and state in {"idle", "cruise"}:
            residuals["checks"].append({
                "name": "oxygen_sensor_lean_signal",
                "value": o2_v,
                "status": "lean_o2_signal",
            })

        return residuals

    def evaluate_ve_obstruction(self, telemetry: Dict[str, Any], current_ve: float) -> Optional[str]:
        """
        Evaluates breathing efficiency under high load/WOT (TPS/LOAD > 85%, RPM > 3500).
        Flags physical exhaust/catalytic restrictions when VE falls below 70% of baseline.
        """
        rpm = telemetry.get("RPM", 0.0)
        load = telemetry.get("LOAD", 0.0)
        map_kpa = telemetry.get("MAP", 101.3)
        baro_kpa = telemetry.get("BARO", self.baro_kpa_default)

        is_wot_condition = (load >= 85.0 or telemetry.get("TPS", 0.0) >= 85.0) and (rpm >= 3500.0)
        if not is_wot_condition:
            return None

        is_at_atmospheric = map_kpa >= (baro_kpa - 5.0)
        ve_threshold = self.expected_wot_ve * 0.70

        if is_at_atmospheric and current_ve < ve_threshold:
            return (
                f"PHYSICAL_OBSTRUCTION_ALERT: Volumetric Efficiency restricted ({current_ve*100.0:.1f}% vs "
                f"baseline {self.expected_wot_ve*100.0:.1f}%) under WOT at {rpm:.0f} RPM. "
                "Suspect catalytic converter clogging or exhaust path restriction."
            )
        return None

    def track_o2_sensor_kinetics(self, telemetry: Dict[str, Any]) -> Tuple[float, Optional[str]]:
        """
        Monitors O2 Bank 1 Sensor 1 voltage oscillations (0.1V - 0.9V) centered around 0.45V.
        Tracks zero-crossing frequency over a sliding 5.0s window during closed-loop (ECT > 80°C).
        Flags sluggish sensor poisoning decay when switching frequency drops below 0.5 Hz.
        """
        now = time.time()
        o2_volts = telemetry.get("O2_V")
        coolant_temp = telemetry.get("COOLANT", 0)

        if o2_volts is None:
            return 0.0, None

        self._o2_history.append((now, float(o2_volts)))
        while self._o2_history and (now - self._o2_history[0][0]) > 5.0:
            self._o2_history.popleft()

        is_high = float(o2_volts) >= 0.45
        if self._last_o2_state_high is not None and is_high != self._last_o2_state_high:
            self._o2_switch_timestamps.append(now)
        self._last_o2_state_high = is_high

        while self._o2_switch_timestamps and (now - self._o2_switch_timestamps[0]) > 5.0:
            self._o2_switch_timestamps.popleft()

        window_duration = 5.0
        num_crossings = len(self._o2_switch_timestamps)
        full_cycles = num_crossings / 2.0
        freq_hz = full_cycles / window_duration
        self.latest_o2_frequency_hz = round(freq_hz, 2)

        is_closed_loop = coolant_temp >= 80 and telemetry.get("RPM", 0) > 600
        alert = None

        if is_closed_loop and len(self._o2_history) >= 10:
            if self.latest_o2_frequency_hz < 0.5:
                alert = (
                    f"SENSOR_KINETIC_DEGRADATION: O2 switching frequency decayed to "
                    f"{self.latest_o2_frequency_hz:.2f} Hz (< 0.5 Hz nominal). "
                    "Pre-DTC P0133 sensor sluggishness/chemical poisoning warning."
                )

        return self.latest_o2_frequency_hz, alert

    def evaluate_fuel_trim_matrix(self, telemetry: Dict[str, Any]) -> List[str]:
        """
        Populates a 3x3 Load-Cell Matrix with Total Trim (STFT + LTFT) and evaluates
        differential fuel delivery across operating load states.
        """
        insights = []
        stft = telemetry.get("STFT", 0.0)
        ltft = telemetry.get("LTFT", 0.0)
        total_trim = stft + ltft
        rpm = telemetry.get("RPM", 0.0)
        load = telemetry.get("LOAD", 0.0)

        if rpm < 1200:
            rpm_key = "RPM_LOW"
        elif rpm <= 3000:
            rpm_key = "RPM_MID"
        else:
            rpm_key = "RPM_HIGH"

        if load < 30.0:
            load_key = "LOAD_LOW"
        elif load <= 70.0:
            load_key = "LOAD_MID"
        else:
            load_key = "LOAD_HIGH"

        curr_val = self.fuel_trim_matrix[rpm_key][load_key]
        if curr_val is None:
            self.fuel_trim_matrix[rpm_key][load_key] = total_trim
        else:
            self.fuel_trim_matrix[rpm_key][load_key] = (0.8 * curr_val) + (0.2 * total_trim)

        low_idle_trim = self.fuel_trim_matrix["RPM_LOW"]["LOAD_LOW"]
        mid_cruise_trim = self.fuel_trim_matrix["RPM_MID"]["LOAD_MID"]
        high_load_trim = self.fuel_trim_matrix["RPM_HIGH"]["LOAD_HIGH"]

        if low_idle_trim is not None and low_idle_trim > 12.0:
            if mid_cruise_trim is not None and mid_cruise_trim < 5.0:
                insights.append(
                    f"ROOT_CAUSE_ISOLATED: Intake Vacuum Leak downstream of throttle. "
                    f"(Idle Trim: +{low_idle_trim:.1f}%, Cruise Trim: {mid_cruise_trim:.1f}%)"
                )

        if high_load_trim is not None and high_load_trim > 12.0:
            if low_idle_trim is not None and low_idle_trim < 6.0:
                insights.append(
                    f"ROOT_CAUSE_ISOLATED: Fuel Delivery Restriction (weak pump / clogged fuel filter). "
                    f"(High Load Trim: +{high_load_trim:.1f}%, Idle Trim: {low_idle_trim:.1f}%)"
                )

        cells = [v for r in self.fuel_trim_matrix.values() for v in r.values() if v is not None]
        if len(cells) >= 4 and all(val > 10.0 for val in cells):
            insights.append(
                "ROOT_CAUSE_ISOLATED: Global Lean Shift across all load cells. "
                "Check MAF calibration scaling, fuel pressure regulator, or exhaust manifold pre-O2 leak."
            )

        return insights

    def isolate_root_dtcs(self, active_dtcs: List[str]) -> Dict[str, Any]:
        """
        Traverses the Parent-Child Directed Acyclic Graph (DAG) to isolate true
        root-cause failure codes and suppress secondary downstream symptoms.
        """
        active_set = set(active_dtcs)
        suppressed_codes = set()

        for parent, children in self.dependency_graph.items():
            if parent in active_set:
                suppressed_codes.update(children.intersection(active_set))

        unmasked_primaries = [code for code in active_dtcs if code not in suppressed_codes]

        return {
            "root_causes": unmasked_primaries,
            "suppressed_symptom_codes": sorted(list(suppressed_codes)),
            "raw_input_codes": active_dtcs,
        }

