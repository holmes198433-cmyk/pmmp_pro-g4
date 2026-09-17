"""
Scenario-based validation tests for autonomous diagnostics.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulate import run_scenario, SCENARIOS


class TestScenarioValidation(unittest.TestCase):
    """Validate that the simulation harness produces the expected diagnostic ranking."""

    def test_vacuum_leak_scenario(self):
        self.assertTrue(run_scenario("vacuum_leak"))

    def test_maf_drift_scenario(self):
        self.assertTrue(run_scenario("maf_drift"))

    def test_fuel_delivery_scenario(self):
        self.assertTrue(run_scenario("fuel_delivery_restriction"))

    def test_available_scenarios(self):
        self.assertIn("healthy", SCENARIOS)
        self.assertIn("vacuum_leak", SCENARIOS)
        self.assertIn("maf_drift", SCENARIOS)
        self.assertIn("fuel_delivery_restriction", SCENARIOS)


def run_all_tests():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestScenarioValidation))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    sys.exit(0 if run_all_tests() else 1)

