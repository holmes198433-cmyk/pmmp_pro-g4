"""
Mock OBD Manager for testing without hardware
Simulates real vehicle data
"""

import time
import random
import threading
from typing import Dict, Any, Callable, Optional, List
from utils.logger import get_logger

logger = get_logger(__name__)

class MockOBDManager:
    """Simulates OBD-II hardware with realistic vehicle data"""
    
    def __init__(self, port_name: str = "/dev/mock", fast_init: bool = True):
        self.port_name = port_name
        self.fast_init = fast_init
        self.telemetry_cache: Dict[str, Any] = {
            "RPM": 0,
            "MAF": 0.0,
            "LOAD": 0.0,
            "STFT": 0.0,
            "LTFT": 2.5,  # Slight positive trim at idle
            "COOLANT": 82,
            "O2_V": 0.45,
            "DTCs": []
        }
        self.cache_lock = threading.Lock()
        self.is_running = False
        self.simulation_thread = None
        self._callbacks = {}
        self._active_dtcs = []
        self._simulate_fault = False
        self._fault_type = None
        
    def get_snapshot(self) -> dict:
        """Returns the latest telemetry dictionary (alias for get_telemetry)."""
        return self.get_telemetry()
        
    def initialize_hardware(self) -> bool:
        """Initialize mock hardware (always succeeds)"""
        logger.info(f"[MOCK] Initializing mock OBD device on {self.port_name}")
        time.sleep(0.5)  # Simulate connection delay
        logger.info("[MOCK] Mock device connected successfully!")
        return True
    
    def _subscribe_tiered_commands(self) -> None:
        """Register callbacks for data updates (mock doesn't use this, but API compatible)"""
        logger.debug("[MOCK] Subscribed to tiered commands")
        
    def start_stream(self) -> None:
        """Start simulating vehicle data"""
        if self.is_running:
            logger.warning("[MOCK] Stream already running")
            return
        
        self.is_running = True
        self.simulation_thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self.simulation_thread.start()
        logger.info("[MOCK] Data stream started")
    
    def stop_stream(self) -> None:
        """Stop simulating vehicle data"""
        self.is_running = False
        if self.simulation_thread:
            self.simulation_thread.join(timeout=2)
        logger.info("[MOCK] Data stream stopped")
    
    def is_connected(self) -> bool:
        """Check if device is connected"""
        return True
    
    def _simulation_loop(self) -> None:
        """Generate realistic vehicle telemetry"""
        cycle = 0
        
        while self.is_running:
            cycle += 1
            
            # Simulate different driving scenarios
            if cycle < 10:
                # Cold start idle (0-3 seconds)
                self._update_idle_cold_start()
            elif cycle < 40:
                # Warm idle (3-12 seconds)
                self._update_idle_warm()
            elif cycle < 80:
                # Acceleration (12-24 seconds)
                self._update_acceleration()
            elif cycle < 100:
                # Highway cruise (24-30 seconds)
                self._update_cruise()
            else:
                # Simulate fault at end
                self._simulate_fault = True
                self._fault_type = "lean"
                self._update_fault_condition()
            
            # Simulate fault conditions if enabled
            if self._simulate_fault:
                if cycle % 5 == 0:
                    self._inject_dtc("P0171")  # System Too Lean
            
            time.sleep(0.3)  # Update every 300ms
    
    def _update_idle_cold_start(self):
        """Simulate cold start idle (high RPM, rich mixture)"""
        with self.cache_lock:
            self.telemetry_cache["RPM"] = 1200 + random.randint(-50, 100)
            self.telemetry_cache["LOAD"] = 5 + random.uniform(-1, 2)
            self.telemetry_cache["MAF"] = 3.5 + random.uniform(-0.5, 0.5)
            self.telemetry_cache["STFT"] = -8 + random.uniform(-2, 2)  # Rich
            self.telemetry_cache["LTFT"] = -6 + random.uniform(-1, 1)  # Rich
            self.telemetry_cache["COOLANT"] = max(20, self.telemetry_cache["COOLANT"] + 1)
            self.telemetry_cache["O2_V"] = 0.3 + random.uniform(-0.05, 0.05)
            self.telemetry_cache["_last_updated"] = time.time()
    
    def _update_idle_warm(self):
        """Simulate warm idle (normal RPM, lean control)"""
        with self.cache_lock:
            self.telemetry_cache["RPM"] = 750 + random.randint(-30, 50)
            self.telemetry_cache["LOAD"] = 2 + random.uniform(-0.5, 1)
            self.telemetry_cache["MAF"] = 2.8 + random.uniform(-0.3, 0.3)
            self.telemetry_cache["STFT"] = 1 + random.uniform(-1, 2)  # Slightly lean control
            self.telemetry_cache["LTFT"] = 2.5 + random.uniform(-0.5, 1)  # Lean trim accumulation
            self.telemetry_cache["COOLANT"] = min(95, self.telemetry_cache["COOLANT"] + 0.5)
            self.telemetry_cache["O2_V"] = 0.45 + random.uniform(-0.05, 0.08)
            self.telemetry_cache["_last_updated"] = time.time()
    
    def _update_acceleration(self):
        """Simulate acceleration (rising RPM, dynamic fuel trim)"""
        with self.cache_lock:
            rpm = min(4500, 750 + (random.random() * 3750))
            self.telemetry_cache["RPM"] = rpm
            self.telemetry_cache["LOAD"] = 30 + random.uniform(-5, 15)
            self.telemetry_cache["MAF"] = 8.5 + random.uniform(-2, 3)
            self.telemetry_cache["STFT"] = -2 + random.uniform(-2, 3)  # Dynamic
            self.telemetry_cache["LTFT"] = 1.5 + random.uniform(-1, 2)
            self.telemetry_cache["COOLANT"] = 92 + random.uniform(-2, 2)
            self.telemetry_cache["O2_V"] = 0.5 + random.uniform(-0.1, 0.2)
            self.telemetry_cache["_last_updated"] = time.time()
    
    def _update_cruise(self):
        """Simulate highway cruise (stable RPM and trims)"""
        with self.cache_lock:
            self.telemetry_cache["RPM"] = 2200 + random.randint(-50, 100)
            self.telemetry_cache["LOAD"] = 35 + random.uniform(-3, 5)
            self.telemetry_cache["MAF"] = 9.2 + random.uniform(-0.5, 0.8)
            self.telemetry_cache["STFT"] = 0.5 + random.uniform(-0.5, 1)
            self.telemetry_cache["LTFT"] = 2.0 + random.uniform(-0.3, 0.5)
            self.telemetry_cache["COOLANT"] = 93 + random.uniform(-1, 1)
            self.telemetry_cache["O2_V"] = 0.48 + random.uniform(-0.05, 0.08)
            self.telemetry_cache["_last_updated"] = time.time()
    
    def _update_fault_condition(self):
        """Simulate fault condition (lean condition)"""
        with self.cache_lock:
            self.telemetry_cache["RPM"] = 800 + random.randint(-30, 50)
            self.telemetry_cache["LOAD"] = 5 + random.uniform(0, 2)
            self.telemetry_cache["MAF"] = 2.5 + random.uniform(-0.3, 0.2)  # Lower MAF (intake leak)
            self.telemetry_cache["STFT"] = 8 + random.uniform(-1, 2)  # Positive trim (lean correction)
            self.telemetry_cache["LTFT"] = 10 + random.uniform(-1, 3)  # High LTFT (lean accumulation)
            self.telemetry_cache["COOLANT"] = 88 + random.uniform(-2, 2)
            self.telemetry_cache["O2_V"] = 0.65 + random.uniform(-0.05, 0.1)  # High O2 (lean)
            self.telemetry_cache["_last_updated"] = time.time()
    
    def _inject_dtc(self, code: str):
        """Inject a diagnostic trouble code"""
        with self.cache_lock:
            if code not in self.telemetry_cache["DTCs"]:
                self.telemetry_cache["DTCs"].append(code)
                logger.warning(f"[MOCK] DTC injected: {code}")
    
    def query_active_dtcs(self) -> List[str]:
        """Get active diagnostic trouble codes"""
        with self.cache_lock:
            return self.telemetry_cache["DTCs"].copy()
    
    def get_telemetry(self) -> Dict[str, Any]:
        """Get current telemetry snapshot"""
        with self.cache_lock:
            return self.telemetry_cache.copy()
    
    def clear_dtcs(self) -> bool:
        """Clear all active DTCs"""
        with self.cache_lock:
            was_empty = len(self.telemetry_cache["DTCs"]) == 0
            self.telemetry_cache["DTCs"].clear()
            self._simulate_fault = False
            logger.info("[MOCK] All DTCs cleared")
            return not was_empty
    
    def register_callback(self, label: str, callback: Callable):
        """Register callback for data updates (API compatible)"""
        self._callbacks[label] = callback
