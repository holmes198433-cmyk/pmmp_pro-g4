import sys
import os
import time

from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox, QLineEdit
from PyQt6.QtCore import QTimer

from async_obd_manager import AsyncOBDManager
from mock_obd_manager import MockOBDManager
from thermo_diagnostics import ThermodynamicDiagnosticEngine
from rag_diagnostics_engine import LocalServiceManualRAG
from gui_dashboard import PMMPProDash
from utils.config import init_config, get_config
from utils.logger import get_logger

logger = get_logger(__name__)

class PMMPController:
    def __init__(self, use_mock: bool = False):
        # Initialize configuration
        env = os.getenv('PMMP_ENV', 'production')
        self.config = init_config(env)
        logger.info(f"PMMP Pro-G4 initialized in {self.config.env} mode")
        
        self.app = QApplication(sys.argv)
        self.gui = PMMPProDash()
        self.use_mock = use_mock
        
        # Wire up console input handler
        self.gui.console_input.returnPressed.connect(self.handle_console_command)
        
        # Initialize engines from config
        try:
            obd_config = self.config.get_section('obd')
            
            # Use mock manager if requested or in development
            if self.use_mock or env == 'development':
                self.obd_mgr = MockOBDManager()
                logger.info("Using MOCK OBD Manager for testing")
            else:
                self.obd_mgr = AsyncOBDManager(
                    port_name=obd_config.get('port'),
                    fast_init=obd_config.get('fast_init', True)
                )
            logger.info(f"OBD Manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize OBD Manager: {e}")
            self.obd_mgr = None
        
        try:
            engine_config = self.config.get_section('engine')
            self.physics_engine = ThermodynamicDiagnosticEngine(
                displacement_liters=engine_config.get('displacement_liters', 2.0)
            )
            logger.info(f"Physics Engine initialized: {engine_config.get('displacement_liters')}L")
        except Exception as e:
            logger.error(f"Failed to initialize Physics Engine: {e}")
            self.physics_engine = None
        
        try:
            rag_config = self.config.get_section('rag')
            self.rag_engine = LocalServiceManualRAG(
                manual_db_path=rag_config.get('manual_db_path', './service_manuals')
            )
            logger.info("RAG Diagnostics Engine initialized")
        except Exception as e:
            logger.error(f"Failed to initialize RAG Engine: {e}")
            self.rag_engine = None
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.system_tick)
        
        self.diagnostic_cycle_counter = 0
        self.active_dtcs = []
        self.last_dtc_analysis = {}

    def start(self):
        """Start the application."""
        try:
            if self.obd_mgr:
                if self.obd_mgr.initialize_hardware():
                    self.obd_mgr.start_stream()
                    mode = "MOCK" if self.use_mock else "HARDWARE"
                    logger.info(f"OBD stream started in {mode} mode")
                    self.gui.console_output.append(f"✅ OBD Device initialized ({mode} mode)")
                else:
                    logger.warning("Hardware not detected. Running in mock mode.")
                    self.gui.console_output.append("⚠️  WARNING: Hardware not detected.")
            else:
                logger.warning("OBD Manager not available.")
                self.gui.console_output.append("⚠️  WARNING: OBD Manager not initialized.")
            
            gui_config = self.config.get_section('gui')
            refresh_rate = gui_config.get('refresh_rate_ms', 50)
            
            self.gui.show()
            self.timer.start(refresh_rate)
            logger.info(f"GUI started (refresh rate: {refresh_rate}ms)")
            self.gui.console_output.append("✅ System ready. Type 'HELP' for commands.")
            
            exit_code = self.app.exec()
        except Exception as e:
            logger.error(f"Error during startup: {e}")
            if self.gui:
                self.gui.show_error(f"Startup failed: {e}")
            raise
        finally:
            if self.obd_mgr:
                self.obd_mgr.stop_stream()
            logger.info("Application shutting down")
            sys.exit(exit_code if exit_code else 0)
    
    def system_tick(self):
        """Called periodically to update system state. THIS IS THE DATA PIPELINE."""
        try:
            self.diagnostic_cycle_counter += 1
            
            # STEP 1: Get telemetry from OBD manager
            telemetry = self._get_telemetry()
            
            # STEP 2: Analyze DTCs
            active_dtcs = self.obd_mgr.query_active_dtcs() if self.obd_mgr else []
            dtc_analysis = self._analyze_dtcs(active_dtcs) if self.physics_engine else {}
            
            # STEP 3: Get RAG procedures for root causes
            rag_data = self._get_rag_data(dtc_analysis) if self.rag_engine else {}
            
            # STEP 4: Update GUI with all data
            if self.gui:
                self.gui.update_ui(telemetry, dtc_analysis, rag_data)
            
            # Store for console commands
            self.active_dtcs = active_dtcs
            self.last_dtc_analysis = dtc_analysis
            
        except Exception as e:
            logger.error(f"Error in system tick: {e}")
    
    def _get_telemetry(self) -> dict:
        """STEP 1: Get current vehicle telemetry from OBD manager"""
        if not self.obd_mgr:
            return {
                "RPM": 0, "LOAD": 0.0, "STFT": 0.0,
                "LTFT": 0.0, "COOLANT": 0, "MAF": 0.0,
                "O2_V": 0.0
            }
        
        try:
            if hasattr(self.obd_mgr, 'get_telemetry'):
                # Mock manager
                return self.obd_mgr.get_telemetry()
            else:
                # Real OBD manager
                telemetry = self.obd_mgr.telemetry_cache.copy() if hasattr(self.obd_mgr, 'telemetry_cache') else {}
                return telemetry
        except Exception as e:
            logger.debug(f"Error getting telemetry: {e}")
            return {}
    
    def _analyze_dtcs(self, active_dtcs: list) -> dict:
        """STEP 2: Use physics engine to analyze DTCs"""
        if not self.physics_engine or not active_dtcs:
            return {
                "root_causes": [],
                "suppressed_symptom_codes": []
            }
        
        try:
            return self.physics_engine.isolate_root_dtcs(active_dtcs)
        except Exception as e:
            logger.error(f"Error analyzing DTCs: {e}")
            return {"root_causes": [], "suppressed_symptom_codes": []}
    
    def _get_rag_data(self, dtc_analysis: dict) -> dict:
        """STEP 3: Get RAG procedures for root cause codes"""
        if not self.rag_engine:
            return {}
        
        root_causes = dtc_analysis.get('root_causes', [])
        if not root_causes:
            return {}
        
        try:
            # Get procedure for first root cause
            primary_code = root_causes[0]
            return self.rag_engine.query_diagnostic_procedure(primary_code)
        except Exception as e:
            logger.error(f"Error getting RAG data: {e}")
            return {}
    
    def handle_console_command(self):
        """Handle console input commands."""
        try:
            cmd = self.gui.console_input.text().strip()
            self.gui.console_input.clear()
            
            if not cmd:
                return
            
            logger.debug(f"Console command received: {cmd}")
            self.gui.console_output.append(f">> {cmd}")
            
            # Parse command
            parts = cmd.upper().split()
            command = parts[0] if parts else ""
            
            if command == "HELP":
                self._show_help()
            elif command == "ATZ":
                self._reset_device()
            elif command == "DTC":
                self._read_dtc()
            elif command == "LIVE":
                self._toggle_live_data()
            elif command == "CLEAR":
                self._clear_dtcs()
            elif command == "STATUS":
                self._show_status()
            elif command == "EXIT" or command == "QUIT":
                self.app.quit()
            else:
                self.gui.console_output.append(f"❌ Unknown command: {command}. Type HELP for available commands.")
        except Exception as e:
            logger.error(f"Error handling console command: {e}")
            self.gui.console_output.append(f"❌ Error: {e}")
    
    def _show_help(self):
        """Display available commands."""
        help_text = """
╔════════════════════════════════════════════════════════╗
║           PMMP Pro-G4 Console Commands                ║
╚════════════════════════════════════════════════════════╝

Commands:
  HELP              - Show this message
  ATZ               - Reset device & clear DTCs
  DTC               - Read and analyze active DTCs
  LIVE              - Toggle live telemetry display
  STATUS            - Show system status
  CLEAR             - Clear active DTCs
  EXIT/QUIT         - Exit application

Examples:
  >> HELP
  >> DTC
  >> ATZ
"""
        self.gui.console_output.append(help_text)
        logger.info("Help message displayed")
    
    def _reset_device(self):
        """Reset OBD device and clear DTCs."""
        try:
            if self.obd_mgr:
                self.gui.console_output.append("🔄 Resetting device and clearing DTCs...")
                
                if hasattr(self.obd_mgr, 'clear_dtcs'):
                    self.obd_mgr.clear_dtcs()
                    self.gui.console_output.append("✅ DTCs cleared successfully")
                    logger.info("DTCs cleared")
                else:
                    self.gui.console_output.append("✅ Device reset command sent")
                    logger.info("Reset command sent to OBD device")
            else:
                self.gui.console_output.append("❌ OBD Manager not available")
        except Exception as e:
            logger.error(f"Error resetting device: {e}")
            self.gui.console_output.append(f"❌ Reset failed: {e}")
    
    def _read_dtc(self):
        """Read and display active DTCs with analysis."""
        try:
            if not self.obd_mgr:
                self.gui.console_output.append("❌ OBD Manager not available")
                return
            
            active_dtcs = self.obd_mgr.query_active_dtcs()
            
            if not active_dtcs:
                self.gui.console_output.append("✅ No active DTCs detected")
                logger.info("DTC read: No active codes")
                return
            
            # Display DTCs
            self.gui.console_output.append(f"📋 Active DTCs ({len(active_dtcs)}):")
            for code in active_dtcs:
                self.gui.console_output.append(f"   • {code}")
            
            # Show analysis if available
            if self.last_dtc_analysis:
                roots = self.last_dtc_analysis.get('root_causes', [])
                suppressed = self.last_dtc_analysis.get('suppressed_symptom_codes', [])
                
                if roots:
                    self.gui.console_output.append(f"\n🔍 Root Causes:")
                    for code in roots:
                        self.gui.console_output.append(f"   • {code}")
                
                if suppressed:
                    self.gui.console_output.append(f"\n🔗 Suppressed Symptom Codes:")
                    for code in suppressed:
                        self.gui.console_output.append(f"   • {code}")
            
            logger.info(f"DTC read: {active_dtcs}")
        except Exception as e:
            logger.error(f"Error reading DTCs: {e}")
            self.gui.console_output.append(f"❌ Error: {e}")
    
    def _toggle_live_data(self):
        """Toggle live data stream display."""
        try:
            self.gui.console_output.append("📡 Telemetry Stream:")
            
            # Get current telemetry
            telemetry = self._get_telemetry()
            
            if telemetry:
                self.gui.console_output.append(f"   RPM: {telemetry.get('RPM', 0):.0f}")
                self.gui.console_output.append(f"   LOAD: {telemetry.get('LOAD', 0):.1f}%")
                self.gui.console_output.append(f"   MAF: {telemetry.get('MAF', 0):.1f} g/s")
                self.gui.console_output.append(f"   STFT: {telemetry.get('STFT', 0):.1f}%")
                self.gui.console_output.append(f"   LTFT: {telemetry.get('LTFT', 0):.1f}%")
                self.gui.console_output.append(f"   COOLANT: {telemetry.get('COOLANT', 0):.0f}°C")
                self.gui.console_output.append(f"   O2_V: {telemetry.get('O2_V', 0):.2f}V")
            else:
                self.gui.console_output.append("   (No data available)")
            
            logger.info("Live data displayed")
        except Exception as e:
            logger.error(f"Error displaying live data: {e}")
            self.gui.console_output.append(f"❌ Error: {e}")
    
    def _clear_dtcs(self):
        """Clear active DTCs."""
        try:
            if not self.obd_mgr:
                self.gui.console_output.append("❌ OBD Manager not available")
                return
            
            if hasattr(self.obd_mgr, 'clear_dtcs'):
                self.obd_mgr.clear_dtcs()
                self.gui.console_output.append("✅ All DTCs cleared")
                logger.info("DTCs cleared")
            else:
                self.gui.console_output.append("❌ Clear DTCs not supported")
        except Exception as e:
            logger.error(f"Error clearing DTCs: {e}")
            self.gui.console_output.append(f"❌ Error: {e}")
    
    def _show_status(self):
        """Display system status."""
        try:
            mode = "MOCK" if self.use_mock else "HARDWARE"
            env = self.config.env.upper()
            
            status_text = f"""
╔════════════════════════════════════════════════════════╗
║              System Status                             ║
╚════════════════════════════════════════════════════════╝
Environment: {env}
Mode: {mode}
OBD Status: {'Connected' if self.obd_mgr else 'Disconnected'}
Active DTCs: {len(self.active_dtcs)}
Cycle: {self.diagnostic_cycle_counter}
"""
            self.gui.console_output.append(status_text)
            logger.info(f"Status displayed: {mode} mode, {len(self.active_dtcs)} DTCs")
        except Exception as e:
            logger.error(f"Error showing status: {e}")
            self.gui.console_output.append(f"❌ Error: {e}")
        parts = cmd.split()
        upper_cmd = parts[0].upper()
        
        # Built-in utility commands
        if upper_cmd == "CLEAR":
            self.gui.console_output.clear()
            return
        elif upper_cmd == "HELP":
            self.gui.console_output.append("--- REVERSE ENGINEERING / RAW TERMINAL COMMANDS ---")
            self.gui.console_output.append("  HEADER <id>        - Set ELM327 CAN header (e.g., HEADER 726)")
            self.gui.console_output.append("  RAW <hex>          - Send raw hex payload directly")
            self.gui.console_output.append("  SCAN               - Sweep standard ECU/BCM CAN IDs for active responses")
            self.gui.console_output.append("  UDS_READ <did>     - Read Data By Identifier (Service 22, e.g., UDS_READ F190)")
            self.gui.console_output.append("  UDS_CTRL <did> <v> - Input/Output Control (Service 2F, e.g., UDS_CTRL 0301 03)")
            self.gui.console_output.append("  STATUS, DTC, CLEAR")
            return
        elif upper_cmd == "STATUS":
            status = "CONNECTED" if self.obd_mgr.connection and self.obd_mgr.connection.is_connected() else "OFFLINE"
            self.gui.console_output.append(f"Hardware Status: {status}")
            return
        elif upper_cmd == "DTC":
            dtcs = self.obd_mgr.query_active_dtcs()
            self.gui.console_output.append(f"Active DTCs: {dtcs}")
            return
            
        # Check active hardware connection before passing raw protocol commands
        if not self.obd_mgr.connection or not self.obd_mgr.connection.interface:
            self.gui.console_output.append("Error: Hardware interface not active. Run controller connected to vehicle.")
            return

        interface = self.obd_mgr.connection.interface

        try:
            if upper_cmd == "HEADER" and len(parts) > 1:
                can_id = parts[1]
                resp = interface.send(f"AT SH {can_id}")
                self.gui.console_output.append(f"CAN Header set to {can_id}: {resp}")
                
            elif upper_cmd == "RAW":
                raw_payload = " ".join(parts[1:])
                resp = interface.send(raw_payload)
                self.gui.console_output.append(f"Response: {resp}")
                
            elif upper_cmd == "UDS_READ" and len(parts) > 1:
                did = parts[1]
                # Service 22: Read Data By Identifier
                payload = f"22 {did}"
                resp = interface.send(payload)
                self.gui.console_output.append(f"UDS Read [{did}] -> {resp}")
                
            elif upper_cmd == "UDS_CTRL" and len(parts) > 2:
                did = parts[1]
                param = parts[2]
                # Service 2F: Input/Output Control By Identifier (Common for actuators/locks)
                payload = f"2F {did} {param}"
                resp = interface.send(payload)
                self.gui.console_output.append(f"UDS Control [{did}] param {param} -> {resp}")
                
            elif upper_cmd == "SCAN":
                self.gui.console_output.append("Scanning standard module CAN IDs...")
                active_nodes = []
                test_ids = [0x7E0, 0x7E1, 0x7E2, 0x726, 0x730, 0x740, 0x750, 0x760]
                for node_id in test_ids:
                    id_hex = f"{node_id:03X}"
                    interface.send(f"AT SH {id_hex}")
                    # Tester Present (Service 3E, Subfunction 00 - keep alive / check presence)
                    resp = interface.send("3E 00")
                    if resp and "NO DATA" not in str(resp) and "Error" not in str(resp) and "?" not in str(resp):
                        active_nodes.append(id_hex)
                        self.gui.console_output.append(f"  [+] Active Node Found: 0x{id_hex} -> {resp}")
                
                # Reset header back to standard powertrain default (7E0)
                interface.send("AT SH 7E0")
                self.gui.console_output.append(f"Scan complete. Found {len(active_nodes)} responding modules.")
                
            else:
                # Direct fallback for standard raw text entry
                resp = interface.send(cmd)
                self.gui.console_output.append(str(resp))
                
        except Exception as e:
            self.gui.console_output.append(f"Error executing command: {e}")
            
    def system_tick(self):
        telemetry = self.obd_mgr.get_snapshot()

        ve = self.physics_engine.calculate_volumetric_efficiency(telemetry)
        telemetry["VE"] = round(ve * 100.0, 1)
        self.physics_engine.evaluate_fuel_trim_matrix(telemetry)

        self.diagnostic_cycle_counter += 1
        if self.diagnostic_cycle_counter >= 100: 
            self.active_dtcs = self.obd_mgr.query_active_dtcs()
            self.diagnostic_cycle_counter = 0

            if not self.active_dtcs:
                self.active_dtcs = ["P0101", "P0171", "P0300"]

        dtc_analysis = self.physics_engine.isolate_root_dtcs(self.active_dtcs)

        rag_details = {}
        if dtc_analysis["root_causes"]:
            primary_code = dtc_analysis["root_causes"][0]
            rag_details = self.rag_engine.query_diagnostic_procedure(primary_code)

        self.gui.update_ui(telemetry, dtc_analysis, rag_details)

if __name__ == "__main__":
    # Note: We need a temporary QApplication instance just to show the password dialog 
    # before launching the controller's main application loop.
    temp_app = QApplication(sys.argv)
    
    # --- STARTUP PASSWORD LOCK ---
    SHOP_PASSWORD = "pmmp"  
    authenticated = False
    
    for attempt in range(3):
        password, ok = QInputDialog.getText(
            None, 
            "PMMP Pro-Dash Security", 
            "Enter Workshop Terminal Password:", 
            QLineEdit.EchoMode.Password
        )
        
        if not ok:
            sys.exit(0)
            
        if password == SHOP_PASSWORD:
            authenticated = True
            break
        else:
            remaining = 2 - attempt
            if remaining > 0:
                QMessageBox.warning(None, "Access Denied", f"Incorrect password. {remaining} attempts remaining.")
            
    if not authenticated:
        QMessageBox.critical(None, "Locked Out", "Too many failed attempts. Terminating session.")
        sys.exit(1)
        
    # Clean up temporary app instance so PMMPController initializes its own cleanly
    del temp_app

    controller = PMMPController()
    controller.start()
