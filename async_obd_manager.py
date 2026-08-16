import re
import time
import logging
import threading
from typing import Dict, Any, Callable, Optional, List

import obd
from obd import OBDStatus

logger = logging.getLogger("PMMP_OBD")

class AsyncOBDManager:
    def __init__(self, port_name: Optional[str] = "/dev/ttyUSB0", fast_init: bool = True):
        self.port_name = port_name
        self.fast_init = fast_init
        self.connection: Optional[obd.Async] = None
        self.telemetry_cache: Dict[str, Any] = {
            "RPM": 0, "MAF": 0, "LOAD": 0, "STFT": 0, "LTFT": 0, 
            "COOLANT": 0, "MAP": 101.3, "IAT": 25.0, "O2_V": 0.0, "DTCs": []
        }
        self.vin: Optional[str] = None
        self.freeze_frame_cache: Dict[str, Dict[str, Any]] = {}
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
        
    def query_vin(self) -> Optional[str]:
        """
        Queries 17-digit VIN via Mode 09 PID 02 (ISO 3779 standard).
        Returns validated alphanumeric VIN string excluding letters I, O, Q.
        """
        if self.vin:
            return self.vin

        if not self.connection or not self.connection.is_connected():
            return None

        try:
            # Mode 09 PID 02: Vehicle Identification Number
            resp = self.connection.query(obd.commands.VIN)
            if resp and not resp.is_null():
                raw_vin = str(resp.value).strip().upper()
                # Validate 17-character ISO 3779 pattern
                match = re.search(r'[A-HJ-NPR-Z0-9]{17}', raw_vin)
                if match:
                    self.vin = match.group(0)
                    logger.info(f"Successfully extracted VIN: {self.vin}")
                    return self.vin
        except Exception as e:
            logger.warning(f"Mode 09 PID 02 VIN extraction error: {e}")

        # Interface direct fallback (0902 query)
        try:
            if hasattr(self.connection, 'interface') and self.connection.interface:
                raw_resp = self.connection.interface.send("0902")
                clean = re.sub(r'[^A-HJ-NPR-Z0-9]', '', str(raw_resp).upper())
                match = re.search(r'[A-HJ-NPR-Z0-9]{17}', clean)
                if match:
                    self.vin = match.group(0)
                    return self.vin
        except Exception as e:
            logger.debug(f"Direct 0902 fallback failed: {e}")

        return None

    def query_freeze_frame(self, dtc: Optional[str] = None) -> Dict[str, Any]:
        """
        Acquires Mode 02 Freeze-Frame PID snapshot for an active fault code.
        Captures engine state at the exact moment the DTC threshold triggered.
        """
        if not self.connection or not self.connection.is_connected():
            return {}

        cache_key = dtc or "DEFAULT"
        if cache_key in self.freeze_frame_cache:
            return self.freeze_frame_cache[cache_key]

        snapshot: Dict[str, Any] = {"DTC": dtc}
        try:
            # Mode 02 Freeze Frame Queries
            ff_dtc = self.connection.query(obd.commands.FREEZE_DTC)
            if ff_dtc and not ff_dtc.is_null():
                snapshot["FREEZE_DTC"] = str(ff_dtc.value)

            # Query operational environment metrics at time of fault
            cmds = [
                (obd.commands.RPM, "RPM"),
                (obd.commands.ENGINE_LOAD, "LOAD"),
                (obd.commands.COOLANT_TEMP, "COOLANT"),
                (obd.commands.SPEED, "SPEED"),
                (obd.commands.SHORT_TERM_FUEL_TRIM_1, "STFT"),
                (obd.commands.LONG_TERM_FUEL_TRIM_1, "LTFT")
            ]
            for cmd, key in cmds:
                res = self.connection.query(cmd)
                if res and not res.is_null():
                    snapshot[key] = res.value.magnitude if hasattr(res.value, "magnitude") else res.value

            self.freeze_frame_cache[cache_key] = snapshot
            logger.info(f"Captured Mode 02 Freeze Frame for {cache_key}: {snapshot}")
        except Exception as e:
            logger.warning(f"Error querying Mode 02 Freeze Frame: {e}")

        return snapshot

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
