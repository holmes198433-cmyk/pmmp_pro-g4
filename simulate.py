#!/usr/bin/env python3
"""
PMMP Pro-G4 Simulation Runner
Runs configured fault scenarios for autonomous diagnostic validation.
"""

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from mock_obd_manager import MockOBDManager
from thermo_diagnostics import ThermodynamicDiagnosticEngine
from decision_engine import BayesianDecisionEngine


@dataclass
class Scenario:
    """A deterministic vehicle fault scenario used for diagnosis validation."""
    name: str
    description: str
    telemetry: Dict[str, Any]
    expected_root_causes: List[str] = field(default_factory=list)
    expected_next_tests: List[str] = field(default_factory=list)
    dtcs: List[str] = field(default_factory=list)


def _scenario_base() -> Dict[str, Any]:
    return {
        "RPM": 850,
        "LOAD": 18.0,
        "MAF": 5.2,
        "MAP": 101.3,
        "IAT": 25.0,
        "STFT": 1.0,
        "LTFT": 2.0,
        "COOLANT": 90,
        "O2_V": 0.45,
        "VE": 78.0,
    }


def build_scenario_healthy() -> Scenario:
    return Scenario(
        name="healthy",
        description="Healthy engine baseline with no active fault conditions.",
        telemetry={**_scenario_base(), "RPM": 820, "LOAD": 15.0, "MAF": 5.1, "STFT": 1.0, "LTFT": 1.5},
        expected_root_causes=[],
        expected_next_tests=[],
        dtcs=[],
    )


def build_scenario_vacuum_leak() -> Scenario:
    telemetry = {**_scenario_base(), "RPM": 800, "LOAD": 12.0, "MAF": 3.4, "STFT": 12.0, "LTFT": 11.0, "O2_V": 0.68, "VE": 82.0}
    return Scenario(
        name="vacuum_leak",
        description="Unmetered intake air creates a lean bias at idle and low-load operation.",
        telemetry=telemetry,
        expected_root_causes=["INTAKE_VACUUM_LEAK"],
        expected_next_tests=["smoke_test_intake", "fuel_pressure_check"],
        dtcs=["P0171", "P0174"],
    )


def build_scenario_maf_drift() -> Scenario:
    telemetry = {**_scenario_base(), "RPM": 2100, "LOAD": 38.0, "MAF": 3.0, "MAP": 86.0, "STFT": 11.0, "LTFT": 9.5, "O2_V": 0.74, "VE": 74.0}
    return Scenario(
        name="maf_drift",
        description="Mass airflow sensor drift leads to lean bias across multiple operating regions.",
        telemetry=telemetry,
        expected_root_causes=["MAF_SENSOR_DEGRADATION"],
        expected_next_tests=["maf_calibration_test", "maf_reference_voltage_check"],
        dtcs=["P0101", "P0171"],
    )


def build_scenario_fuel_delivery_restriction() -> Scenario:
    telemetry = {**_scenario_base(), "RPM": 2600, "LOAD": 72.0, "MAF": 7.8, "STFT": 14.0, "LTFT": 16.0, "O2_V": 0.71, "VE": 68.0}
    return Scenario(
        name="fuel_delivery_restriction",
        description="Restricted fuel delivery causes a lean condition under high-load operation.",
        telemetry=telemetry,
        expected_root_causes=["FUEL_DELIVERY_RESTRICTION"],
        expected_next_tests=["fuel_pressure_check", "volume_test", "fuel_filter_inspection"],
        dtcs=["P0087", "P0171"],
    )


SCENARIOS = {
    "healthy": build_scenario_healthy,
    "vacuum_leak": build_scenario_vacuum_leak,
    "maf_drift": build_scenario_maf_drift,
    "fuel_delivery_restriction": build_scenario_fuel_delivery_restriction,
}


def run_scenario(scenario_name: str = "vacuum_leak") -> bool:
    """Run a single deterministic diagnosis scenario and print a structured result."""
    scenario_factory = SCENARIOS.get(scenario_name)
    if scenario_factory is None:
        print(f"Unknown scenario '{scenario_name}'. Available: {', '.join(sorted(SCENARIOS))}")
        return False

    scenario = scenario_factory()
    engine = ThermodynamicDiagnosticEngine(displacement_liters=2.0)
    decision = BayesianDecisionEngine()

    telemetry = dict(scenario.telemetry)
    telemetry["O2_FREQ_HZ"] = 0.4 if "vacuum" in scenario.name or "maf" in scenario.name else 0.7

    # Use the existing physics model to derive insight strings from the scenario data.
    ve = engine.calculate_volumetric_efficiency(telemetry)
    telemetry["VE"] = round(ve * 100.0, 1)
    insights = engine.evaluate_fuel_trim_matrix(telemetry)
    o2_freq, o2_alert = engine.track_o2_sensor_kinetics(telemetry)
    if o2_alert:
        insights.append(o2_alert)

    ve_alert = engine.evaluate_ve_obstruction(telemetry, ve)
    if ve_alert:
        insights.append(ve_alert)

    dtc_analysis = engine.isolate_root_dtcs(scenario.dtcs)
    hypotheses = decision.evaluate(
        dtc_analysis=dtc_analysis,
        physics_insights=insights,
        telemetry=telemetry,
        freeze_frame={
            "RPM": telemetry.get("RPM", 0),
            "LOAD": telemetry.get("LOAD", 0),
        },
    )

    print("=" * 72)
    print(f"Scenario: {scenario.name}")
    print(f"Description: {scenario.description}")
    print(f"Expected root causes: {scenario.expected_root_causes}")
    print("=" * 72)
    print("Telemetry snapshot:")
    for key in ["RPM", "LOAD", "MAF", "MAP", "STFT", "LTFT", "COOLANT", "O2_V", "VE"]:
        print(f"  {key}: {telemetry.get(key)}")
    print()
    print("Physics insights:")
    for insight in insights or ["No additional physics insight detected."]:
        print(f"  - {insight}")
    print()
    print("DTC isolation:")
    print(f"  root_causes={dtc_analysis.get('root_causes', [])}")
    print(f"  suppressed_symptom_codes={dtc_analysis.get('suppressed_symptom_codes', [])}")
    print()
    print("Hypothesis ranking:")
    for idx, hypothesis in enumerate(hypotheses[:5], 1):
        print(f"  {idx}. {hypothesis.hypothesis} ({hypothesis.probability * 100:.1f}% confidence)")
        if hypothesis.supporting_signatures:
            print(f"     Evidence: {', '.join(hypothesis.supporting_signatures[:3])}")
        if hypothesis.next_best_tests:
            print(f"     Next best tests: {', '.join(hypothesis.next_best_tests)}")
    print()
    print("Recommended next tests:")
    recommended = sorted({test for hyp in hypotheses for test in hyp.next_best_tests})
    if recommended:
        for test in recommended:
            print(f"  - {test}")
    else:
        print("  - None. More data collection required.")
    print("=" * 72)

    top = hypotheses[0].hypothesis if hypotheses else "UNKNOWN"
    ok = any(expected in top for expected in scenario.expected_root_causes) or not scenario.expected_root_causes
    if not ok:
        print(f"WARNING: Top diagnosis '{top}' did not match expected root cause(s): {scenario.expected_root_causes}")
    return ok


def print_usage() -> None:
    print("PMMP Pro-G4 Scenario Runner")
    print("Usage: python simulate.py [scenario]")
    print("Available scenarios:")
    for name in sorted(SCENARIOS):
        print(f"  - {name}")


if __name__ == '__main__':
    scenario_name = sys.argv[1] if len(sys.argv) > 1 else "vacuum_leak"
    if scenario_name in {"-h", "--help", "help"}:
        print_usage()
        sys.exit(0)

    start = time.time()
    success = run_scenario(scenario_name)
    elapsed = time.time() - start
    print(f"Scenario run finished in {elapsed:.2f}s")
    sys.exit(0 if success else 1)

