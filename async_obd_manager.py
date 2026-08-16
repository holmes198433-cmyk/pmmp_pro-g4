import obd
from obd import OBDStatus
import time
import logging
import threading
from typing import Dict, Any, Callable, Optional, List

logger = logging.getLogger("PMMP_OBD")

class AsyncOBDManager:
    def __init__(self, port_name: Optional[str] = "/dev/ttyUSB0", fast_init: bool = True):
        self.port_name = port_name
        self.fast_init = fast_init
        self.connection: Optional[obd.Async] = None
        self.telemetry_cache: Dict[str, Any] = {"RPM": 0, "MAF": 0, "LOAD": 0, "STFT": 0, "LTFT": 0, "COOLANT": 0, "DTCs": []}
        self.cache_lock = threading.Lock()
        self.is_running = False
        
    def initialize_hardware(self) -> bool:
        import os
        
        if self.port_name and not os.path.exists(self.port_name):
            logger.warning(f"Target port {self.port_name} not found. Bypassing hardware handshake.")
            return False

        logger.info(f"Establishing connection with OBDLink EX on {self.port_name}...")
        
        try:
            # Wrapped in a safe try-except block to prevent deadlocks/freezes
            self.connection = obd.Async(portstr=self.port_name, baudrate=38400, fast=False, timeout=0.5)
        except Exception as e:
            logger.warning(f"Connection attempt failed or timed out: {e}. Falling back to offline mode.")
            return False

        if not self.connection or self.connection.status() == obd.OBDStatus.NOT_CONNECTED:
            logger.error("Failed to connect to vehicle. Running in offline/mock mode.")
            return False

        logger.info("Hardware connected successfully!")
        return True
        
    def _subscribe_tiered_commands(self) -> None:
        fast_cmds = [(obd.commands.RPM, "RPM"), (obd.commands.MAF, "MAF"), (obd.commands.ENGINE_LOAD, "LOAD")]
        med_cmds = [(obd.commands.SHORT_TERM_FUEL_TRIM_1, "STFT"), (obd.commands.O2_B1S1, "O2_V")]
        slow_cmds = [(obd.commands.LONG_TERM_FUEL_TRIM_1, "LTFT"), (obd.commands.COOLANT_TEMP, "COOLANT")]

        for cmd, label in fast_cmds:
            if self.connection.supports(cmd): 
                self.connection.watch(cmd, callback=self._make_callback(label), weight=1)
        for cmd, label in med_cmds:
            if self.connection.supports(cmd):
                self.connection.watch(cmd, callback=self._make_callback(label), weight=3)
        for cmd, label in slow_cmds:
            if self.connection.supports(cmd):
                self.connection.watch(cmd, callback=self._make_callback(label), weight=10)

    def _make_callback(self, label: str) -> Callable:
        def callback(response):
            with self.cache_lock:
                if not response.is_null():
                    self.telemetry_cache[label] = response.value.magnitude if hasattr(response.value, "magnitude") else response.value
                self.telemetry_cache["_last_updated"] = time.time()
        return callback
        
    def query_active_dtcs(self) -> List[str]:
        if not self.connection or not self.connection.is_connected():
            return []
        try:
            response = self.connection.query(obd.commands.GET_DTC)
            if response and not response.is_null():
                return [code for code, desc in response.value]
        except Exception as e:
            logger.error(f"Error querying DTCs: {e}")
        return []

    def start_stream(self) -> None:
        if self.connection and self.connection.is_connected():
            self._subscribe_tiered_commands()
            self.connection.start()
            self.is_running = True

    def stop_stream(self) -> None:
        if self.connection and self.is_running:
            self.connection.stop()
            self.connection.close()
            self.is_running = False

    def get_snapshot(self) -> Dict[str, Any]:
        with self.cache_lock:
            return dict(self.telemetry_cache)