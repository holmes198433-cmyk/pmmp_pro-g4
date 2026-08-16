#!/usr/bin/env python3
"""
PMMP Pro-G4 - Vehicle Diagnostics System
Main entry point

Usage:
    python main.py              # Run in production/development mode
    python main.py --mock       # Run with mock OBD device
    python main.py --test       # Run tests
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from pmmp_controller import PMMPController
from utils.logger import get_logger

logger = get_logger(__name__)

def main():
    """Entry point for PMMP Pro-G4"""
    
    # Check for command line arguments
    use_mock = '--mock' in sys.argv or os.getenv('PMMP_MOCK') == '1'
    run_tests = '--test' in sys.argv
    
    try:
        if run_tests:
            logger.info("Running tests...")
            # Import test module
            from tests.test_pmmp import run_all_tests
            success = run_all_tests()
            sys.exit(0 if success else 1)
        
        logger.info(f"Starting PMMP Pro-G4 ({'MOCK mode' if use_mock else 'production mode'})...")
        controller = PMMPController(use_mock=use_mock)
        controller.start()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

