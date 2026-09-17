"""
Unit tests for PMMP Pro-G4
Run all tests: python main.py --test
"""

import sys
import os
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config import Config, get_config, init_config
from utils.logger import get_logger
from mock_obd_manager import MockOBDManager
from thermo_diagnostics import ThermodynamicDiagnosticEngine
from rag_diagnostics_engine import LocalServiceManualRAG
from pmmp_controller import PMMPController

logger = get_logger(__name__)


class TestConfiguration(unittest.TestCase):
    """Test configuration system"""

    def test_config_loads(self):
        """Test that config loads without errors"""
        config = Config(env="development")
        self.assertIsNotNone(config)
        self.assertEqual(config.env, "development")

    def test_config_get_simple(self):
        """Test getting simple config values"""
        config = Config(env="development")
        app_name = config.get("app.name")
        self.assertEqual(app_name, "PMMP Pro-G4 (DEV)")

    def test_config_get_nested(self):
        """Test getting nested config values"""
        config = Config(env="development")
        refresh_rate = config.get("gui.refresh_rate_ms")
        self.assertEqual(refresh_rate, 50)

    def test_config_get_section(self):
        """Test getting entire config section"""
        config = Config(env="development")
        obd_config = config.get_section("obd")
        self.assertIn("port", obd_config)
        self.assertIn("baudrate", obd_config)


class TestAutonomyGuardrails(unittest.TestCase):
    """Test safety gating for dangerous operations."""

    def test_passive_mode_blocks_unsafe_actions(self):
        controller = PMMPController.__new__(PMMPController)
        controller.autonomy_level = "PASSIVE"
        controller.gui = SimpleNamespace(console_output=[])

        self.assertFalse(controller._can_execute_action("ATZ", "clear fault memory"))
        self.assertFalse(controller._can_execute_action("RAW", "send raw frame"))

    def test_full_mode_allows_unsafe_actions(self):
        controller = PMMPController.__new__(PMMPController)
        controller.autonomy_level = "FULL"
        controller.gui = SimpleNamespace(console_output=[])

        self.assertTrue(controller._can_execute_action("ATZ", "clear fault memory"))
        self.assertTrue(controller._can_execute_action("RAW", "send raw frame"))

    def test_autonomy_mode_change(self):
        controller = PMMPController.__new__(PMMPController)
        controller.autonomy_level = "RECOMMENDED"
        controller.gui = SimpleNamespace(console_output=[])

        result = controller.set_autonomy_level("ACTIVE")
        self.assertIn("ACTIVE", result)
        self.assertEqual(controller.autonomy_level, "ACTIVE")


class TestMockOBDManager(unittest.TestCase):
    """Test mock OBD manager"""

    def setUp(self):
        self.mgr = MockOBDManager()

    def tearDown(self):
        if hasattr(self.mgr, "is_running") and self.mgr.is_running:
            self.mgr.stop_stream()

    def test_initialization(self):
        """Test mock manager initializes"""
        result = self.mgr.initialize_hardware()
        self.assertTrue(result)

    def test_get_telemetry(self):
        """Test getting telemetry data"""
        telemetry = self.mgr.get_telemetry()
        self.assertIn("RPM", telemetry)
        self.assertIn("LOAD", telemetry)
        self.assertIn("COOLANT", telemetry)
        self.assertIn("DTCs", telemetry)

    def test_start_stop_stream(self):
        """Test stream start/stop"""
        self.mgr.initialize_hardware()
        self.mgr.start_stream()
        self.assertTrue(self.mgr.is_running)

        time.sleep(0.5)
        telemetry = self.mgr.get_telemetry()
        self.assertGreater(telemetry.get("RPM", 0), 0)

        self.mgr.stop_stream()
        self.assertFalse(self.mgr.is_running)

    def test_dtc_injection(self):
        """Test DTC injection"""
        self.mgr.initialize_hardware()
        self.mgr.start_stream()

        time.sleep(1.0)
        dtcs = self.mgr.query_active_dtcs()
        self.assertIsInstance(dtcs, list)

        self.mgr.stop_stream()

    def test_clear_dtcs(self):
        """Test clearing DTCs"""
        self.mgr.initialize_hardware()
        self.mgr._inject_dtc("P0171")

        dtcs = self.mgr.query_active_dtcs()
        self.assertGreater(len(dtcs), 0)

        self.mgr.clear_dtcs()
        dtcs = self.mgr.query_active_dtcs()
        self.assertEqual(len(dtcs), 0)


class TestPhysicsEngine(unittest.TestCase):
    """Test thermodynamic diagnostics engine"""

    def setUp(self):
        self.engine = ThermodynamicDiagnosticEngine(displacement_liters=2.0)

    def test_volumetric_efficiency(self):
        """Test volumetric efficiency calculation"""
        telemetry = {
            "MAF": 5.0,
            "RPM": 2000,
            "MAP": 80.0,
            "IAT": 25.0,
        }
        ve = self.engine.calculate_volumetric_efficiency(telemetry)
        self.assertIsInstance(ve, float)
        self.assertGreaterEqual(ve, 0)

    def test_fuel_trim_analysis(self):
        """Test fuel trim matrix analysis"""
        telemetry = {
            "LTFT": 12.0,
            "RPM": 750,
            "LOAD": 10.0,
        }
        insights = self.engine.evaluate_fuel_trim_matrix(telemetry)
        self.assertIsInstance(insights, list)

    def test_dtc_isolation(self):
        """Test DTC isolation"""
        active_dtcs = ["P0101", "P0171", "P0300"]
        analysis = self.engine.isolate_root_dtcs(active_dtcs)

        self.assertIn("root_causes", analysis)
        self.assertIn("suppressed_symptom_codes", analysis)
        self.assertIsInstance(analysis["root_causes"], list)

    def test_residuals_detect_lean_bias(self):
        telemetry = {
            "RPM": 800,
            "LOAD": 12.0,
            "MAF": 3.0,
            "STFT": 12.0,
            "LTFT": 11.0,
            "O2_V": 0.68,
            "COOLANT": 90,
        }
        residuals = self.engine.evaluate_residuals(telemetry)
        self.assertIn("checks", residuals)
        self.assertTrue(len(residuals["checks"]) >= 1)


class TestRAGEngine(unittest.TestCase):
    """Test RAG diagnostics engine"""

    def setUp(self):
        self.rag = LocalServiceManualRAG()

    def test_query_known_code(self):
        """Test querying known diagnostic code"""
        result = self.rag.query_diagnostic_procedure("P0101")

        self.assertIn("code", result)
        self.assertEqual(result["code"], "P0101")
        self.assertIn("target_component", result)
        self.assertIn("inspection_steps", result)

    def test_query_unknown_code(self):
        """Test querying unknown code"""
        result = self.rag.query_diagnostic_procedure("P9999")

        self.assertIn("code", result)
        self.assertEqual(result["code"], "P9999")
        self.assertIn("target_component", result)
        self.assertEqual(result["target_component"], "Unknown Component")

    def test_pinout_specs(self):
        """Test pinout specifications available"""
        result = self.rag.query_diagnostic_procedure("P0101")
        self.assertIn("pinout_specs", result)
        self.assertIsInstance(result["pinout_specs"], dict)


class TestIntegration(unittest.TestCase):
    """Integration tests for full system"""

    def test_mock_to_physics_to_rag_pipeline(self):
        """Test complete data flow: OBD -> Physics -> RAG"""

        obd = MockOBDManager()
        physics = ThermodynamicDiagnosticEngine()
        rag = LocalServiceManualRAG()

        self.assertTrue(obd.initialize_hardware())
        obd.start_stream()

        try:
            for _ in range(50):
                time.sleep(0.3)
                telemetry = obd.get_telemetry()
                self.assertIn("RPM", telemetry)

                dtcs = obd.query_active_dtcs()
                self.assertIsInstance(dtcs, list)

                if dtcs:
                    analysis = physics.isolate_root_dtcs(dtcs)
                    self.assertIn("root_causes", analysis)

                    if analysis.get("root_causes"):
                        code = analysis["root_causes"][0]
                        rag_result = rag.query_diagnostic_procedure(code)
                        self.assertIn("target_component", rag_result)
                    break
        finally:
            obd.stop_stream()


def run_all_tests():
    """Run all tests and return success status"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestConfiguration))
    suite.addTests(loader.loadTestsFromTestCase(TestAutonomyGuardrails))
    suite.addTests(loader.loadTestsFromTestCase(TestMockOBDManager))
    suite.addTests(loader.loadTestsFromTestCase(TestPhysicsEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestRAGEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

