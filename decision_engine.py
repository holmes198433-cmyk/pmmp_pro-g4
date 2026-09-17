from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class DiagnosticHypothesis:
    """Represents a diagnostic hypothesis with Bayesian probability score and evidentiary signatures."""
    hypothesis: str
    probability: float  # Range 0.0 to 1.0
    primary_dtc: Optional[str] = None
    supporting_signatures: List[str] = field(default_factory=list)
    contradicting_signatures: List[str] = field(default_factory=list)
    suggested_action: str = ""
    next_best_tests: List[str] = field(default_factory=list)
    explanation: str = ""


class BayesianDecisionEngine:
    """
    Bayesian pattern-matching and confidence weighting engine.
    Combines real-time thermodynamic anomalies, Mode 02 freeze-frame context,
    and DTC dependency graph isolations to generate calibrated repair probabilities.
    """

    def __init__(self):
        self.base_priors: Dict[str, float] = {
            "INTAKE_VACUUM_LEAK": 0.30,
            "MAF_SENSOR_DEGRADATION": 0.25,
            "FUEL_DELIVERY_RESTRICTION": 0.20,
            "O2_SENSOR_POISONING": 0.15,
            "EXHAUST_VE_RESTRICTION": 0.10,
        }

        self.next_best_test_map = {
            "INTAKE_VACUUM_LEAK": ["smoke_test_intake", "pcv_test", "evap_purge_check"],
            "MAF_SENSOR_DEGRADATION": ["maf_calibration_test", "maf_reference_voltage_check", "intake_air_leak_check"],
            "FUEL_DELIVERY_RESTRICTION": ["fuel_pressure_check", "fuel_filter_inspection", "volume_test"],
            "O2_SENSOR_POISONING": ["o2_sensor_heater_test", "sensor_response_check", "fuel_trim_validation"],
            "EXHAUST_VE_RESTRICTION": ["backpressure_test", "catalytic_converter_inspection", "exhaust_leak_check"],
        }

    def evaluate(
        self,
        dtc_analysis: Dict[str, Any],
        physics_insights: List[str],
        telemetry: Dict[str, Any],
        freeze_frame: Optional[Dict[str, Any]] = None,
    ) -> List[DiagnosticHypothesis]:
        """
        Calculates posterior probability distribution over potential mechanical failure modes.
        Builds evidence-based rankings that include next-best tests and contextual reasoning.
        """
        scores: Dict[str, float] = dict(self.base_priors)
        signatures: Dict[str, List[str]] = {k: [] for k in scores}
        contradictions: Dict[str, List[str]] = {k: [] for k in scores}

        root_dtcs = dtc_analysis.get("root_causes", [])
        active_raw = dtc_analysis.get("raw_input_codes", [])

        if "P0171" in root_dtcs or "P0174" in root_dtcs or "P0171" in active_raw:
            scores["INTAKE_VACUUM_LEAK"] *= 2.5
            scores["FUEL_DELIVERY_RESTRICTION"] *= 2.0
            scores["MAF_SENSOR_DEGRADATION"] *= 1.8
            signatures["INTAKE_VACUUM_LEAK"].append("DTC P0171/P0174 Active Lean Bias")
            signatures["FUEL_DELIVERY_RESTRICTION"].append("DTC P0171 Active Lean Bias")

        if any(code in root_dtcs or code in active_raw for code in ["P0100", "P0101", "P0102", "P0103"]):
            scores["MAF_SENSOR_DEGRADATION"] *= 4.5
            signatures["MAF_SENSOR_DEGRADATION"].append("Primary MAF Sensor DTC unmasked by causal graph")

        if any(code in root_dtcs or code in active_raw for code in ["P0130", "P0131", "P0133"]):
            scores["O2_SENSOR_POISONING"] *= 4.0
            signatures["O2_SENSOR_POISONING"].append("Primary O2 Circuit/Switching DTC present")

        if any(code in root_dtcs or code in active_raw for code in ["P0087", "P0089"]):
            scores["FUEL_DELIVERY_RESTRICTION"] *= 5.0
            signatures["FUEL_DELIVERY_RESTRICTION"].append("Low Fuel Rail Pressure DTC detected")

        for insight in physics_insights:
            if "Intake Vacuum Leak" in insight:
                scores["INTAKE_VACUUM_LEAK"] *= 4.0
                signatures["INTAKE_VACUUM_LEAK"].append("3x3 Matrix: Elevated trims isolated to idle cell")
            elif "Fuel Delivery Restriction" in insight:
                scores["FUEL_DELIVERY_RESTRICTION"] *= 4.5
                signatures["FUEL_DELIVERY_RESTRICTION"].append("3x3 Matrix: Lean starvation under high RPM/WOT load")
            elif "Global Lean Shift" in insight:
                scores["MAF_SENSOR_DEGRADATION"] *= 2.5
                scores["FUEL_DELIVERY_RESTRICTION"] *= 2.0
                signatures["MAF_SENSOR_DEGRADATION"].append("3x3 Matrix: Global lean shift across all load cells")

        o2_freq = telemetry.get("O2_FREQ_HZ", 1.0)
        if o2_freq > 0.0 and o2_freq < 0.5:
            scores["O2_SENSOR_POISONING"] *= 3.5
            signatures["O2_SENSOR_POISONING"].append(f"O2 switching rate decayed ({o2_freq:.2f} Hz < 0.5 Hz)")

        ve = telemetry.get("VE", 0.0)
        rpm = telemetry.get("RPM", 0.0)
        load = telemetry.get("LOAD", 0.0)
        if load > 80 and rpm > 3500 and ve > 0 and ve < 60.0:
            scores["EXHAUST_VE_RESTRICTION"] *= 5.0
            signatures["EXHAUST_VE_RESTRICTION"].append(f"VE collapse under WOT ({ve:.1f}% @ {rpm:.0f} RPM)")

        if freeze_frame:
            ff_rpm = freeze_frame.get("RPM", 0)
            ff_load = freeze_frame.get("LOAD", 0)
            if ff_rpm < 1100 and ff_load < 30:
                scores["INTAKE_VACUUM_LEAK"] *= 1.8
                signatures["INTAKE_VACUUM_LEAK"].append("Mode 02 Freeze-Frame: Fault set during low-RPM idle")
            elif ff_rpm > 3000 and ff_load > 60:
                scores["FUEL_DELIVERY_RESTRICTION"] *= 1.8
                signatures["FUEL_DELIVERY_RESTRICTION"].append("Mode 02 Freeze-Frame: Fault set under high engine demand")

        # Explicit contradiction logic to avoid false confidence.
        if telemetry.get("MAF", 0) and telemetry.get("LOAD", 0) and telemetry.get("RPM", 0):
            if telemetry.get("MAF", 0) > 12.0 and telemetry.get("LOAD", 0) > 70:
                contradictions["INTAKE_VACUUM_LEAK"].append("MAF is elevated under high load; intake leak less likely")
            if telemetry.get("LTFT", 0) < 0 and telemetry.get("STFT", 0) < 0:
                contradictions["INTAKE_VACUUM_LEAK"].append("Fuel trims are not lean; vacuum leak is less likely")

        total_score = sum(scores.values())
        if total_score <= 0:
            total_score = 1.0

        action_map = {
            "INTAKE_VACUUM_LEAK": "Perform smoke test on intake manifold, PCV lines, and EVAP purge valve.",
            "MAF_SENSOR_DEGRADATION": "Inspect MAF hot-wire element for contamination; verify reference voltage.",
            "FUEL_DELIVERY_RESTRICTION": "Perform fuel volume delivery test and inspect in-tank filter / pump pressure.",
            "O2_SENSOR_POISONING": "Test sensor heater circuit and inspect for silicone/antifreeze contamination.",
            "EXHAUST_VE_RESTRICTION": "Perform exhaust backpressure test at pre-cat O2 sensor port.",
        }

        name_map = {
            "INTAKE_VACUUM_LEAK": "Intake Manifold / Vacuum Leak",
            "MAF_SENSOR_DEGRADATION": "MAF Sensor Contamination / Calibration Drift",
            "FUEL_DELIVERY_RESTRICTION": "Fuel Delivery Deficiency (Pump / Filter / Pressure)",
            "O2_SENSOR_POISONING": "O2 Sensor Kinetic Degradation (Sluggish)",
            "EXHAUST_VE_RESTRICTION": "Exhaust / Catalytic Converter Restriction",
        }

        results: List[DiagnosticHypothesis] = []
        for key, raw_score in scores.items():
            prob = round(raw_score / total_score, 3)
            if prob >= 0.05:
                explanation = (
                    f"Evidence supports {name_map.get(key, key)} based on the active DTCs, fuel-trim behavior, "
                    f"and the current operating state."
                )
                results.append(
                    DiagnosticHypothesis(
                        hypothesis=name_map.get(key, key),
                        probability=prob,
                        primary_dtc=root_dtcs[0] if root_dtcs else None,
                        supporting_signatures=signatures.get(key, []),
                        contradicting_signatures=contradictions.get(key, []),
                        suggested_action=action_map.get(key, "Perform physical inspection."),
                        next_best_tests=self.next_best_test_map.get(key, ["collect_more_data"]),
                        explanation=explanation,
                    )
                )

        results.sort(key=lambda h: h.probability, reverse=True)
        return results

