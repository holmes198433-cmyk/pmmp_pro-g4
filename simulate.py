#!/usr/bin/env python3
"""
PMMP Pro-G4 Simulation Runner
Runs the system without GUI for testing and demonstration
"""

import sys
import os
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from mock_obd_manager import MockOBDManager
from thermo_diagnostics import ThermodynamicDiagnosticEngine
from rag_diagnostics_engine import LocalServiceManualRAG
from utils.config import init_config
from utils.logger import get_logger

logger = get_logger(__name__)


class SimulationEngine:
    """Simulates PMMP Pro-G4 without GUI for testing"""
    
    def __init__(self, scenario: str = "normal"):
        self.scenario = scenario
        self.config = init_config('development')
        
        # Initialize components
        self.obd = MockOBDManager()
        self.physics = ThermodynamicDiagnosticEngine()
        self.rag = LocalServiceManualRAG()
        
        self.cycle = 0
        self.max_cycles = 150  # ~45 seconds
        
    def run_simulation(self):
        """Run full simulation"""
        print("\n" + "="*70)
        print("PMMP Pro-G4 Simulation Engine")
        print("="*70)
        print(f"Scenario: {self.scenario}")
        print(f"Duration: ~{self.max_cycles * 0.3:.0f} seconds")
        print("="*70 + "\n")
        
        # Initialize and start
        logger.info(f"Starting simulation: {self.scenario}")
        
        if not self.obd.initialize_hardware():
            logger.error("Failed to initialize OBD manager")
            return False
        
        self.obd.start_stream()
        
        try:
            while self.cycle < self.max_cycles and not self._should_stop():
                self.cycle += 1
                self._simulation_step()
                time.sleep(0.3)  # 300ms per cycle
        finally:
            self.obd.stop_stream()
            logger.info("Simulation complete")
        
        return True
    
    def _should_stop(self) -> bool:
        """Check if simulation should stop"""
        return False
    
    def _simulation_step(self):
        """Execute one simulation step"""
        # Get telemetry
        telemetry = self.obd.get_telemetry()
        
        # Get DTCs
        dtcs = self.obd.query_active_dtcs()
        
        # Every 10 cycles, print telemetry
        if self.cycle % 10 == 0:
            self._print_telemetry(telemetry, dtcs)
        
        # If DTCs present, analyze
        if dtcs:
            self._analyze_and_display(dtcs)
    
    def _print_telemetry(self, telemetry: dict, dtcs: list):
        """Print telemetry data"""
        print(f"\n[Cycle {self.cycle:3d}] Telemetry Snapshot:")
        print(f"  RPM:      {telemetry.get('RPM', 0):7.0f} RPM")
        print(f"  LOAD:     {telemetry.get('LOAD', 0):7.1f}%")
        print(f"  MAF:      {telemetry.get('MAF', 0):7.1f} g/s")
        print(f"  STFT:     {telemetry.get('STFT', 0):7.1f}%")
        print(f"  LTFT:     {telemetry.get('LTFT', 0):7.1f}%")
        print(f"  COOLANT:  {telemetry.get('COOLANT', 0):7.0f}°C")
        print(f"  O2_V:     {telemetry.get('O2_V', 0):7.2f}V")
        
        if dtcs:
            print(f"  DTCs:     {', '.join(dtcs)}")
    
    def _analyze_and_display(self, dtcs: list):
        """Analyze DTCs and display procedures"""
        print(f"\n>>> DTC Analysis (Active codes: {len(dtcs)})")
        
        for code in dtcs:
            print(f"\n  Code: {code}")
            
            # Get procedures
            procedure = self.rag.query_diagnostic_procedure(code)
            print(f"  Component: {procedure.get('target_component', 'Unknown')}")
            
            # Show inspection steps
            steps = procedure.get('inspection_steps', [])
            if steps:
                print(f"  Inspection Steps:")
                for i, step in enumerate(steps[:3], 1):
                    print(f"    {i}. {step}")
        
        # Get physics analysis
        analysis = self.physics.isolate_root_dtcs(dtcs)
        roots = analysis.get('root_causes', [])
        suppressed = analysis.get('suppressed_symptom_codes', [])
        
        if roots:
            print(f"\n  Root Causes: {', '.join(roots)}")
        if suppressed:
            print(f"  Suppressed Codes: {', '.join(suppressed)}")


def run_scenario(scenario: str) -> bool:
    """Run a specific scenario"""
    sim = SimulationEngine(scenario=scenario)
    return sim.run_simulation()


def print_usage():
    """Print usage information"""
    print("""
PMMP Pro-G4 Simulation Runner
==============================

Usage: python simulate.py [scenario]

Scenarios:
  normal          Run normal simulation with fault injection at end (default)
  test            Run integration test scenario
  demo            Run demonstration with multiple scenarios

Examples:
  python simulate.py normal
  python simulate.py demo
""")


def run_demo():
    """Run complete demonstration"""
    print("\n" + "="*70)
    print("PMMP Pro-G4 Complete Demonstration")
    print("="*70 + "\n")
    
    # Run normal scenario
    print("\n>>> Starting Scenario 1: Normal Operation")
    if not run_scenario("normal"):
        print("❌ Scenario 1 failed")
        return False
    
    print("\n✅ Scenario 1 complete")
    time.sleep(1)
    
    return True


if __name__ == '__main__':
    scenario = sys.argv[1] if len(sys.argv) > 1 else "normal"
    
    if scenario == "help" or scenario == "-h":
        print_usage()
        sys.exit(0)
    elif scenario == "demo":
        success = run_demo()
    else:
        success = run_scenario(scenario)
    
    sys.exit(0 if success else 1)
