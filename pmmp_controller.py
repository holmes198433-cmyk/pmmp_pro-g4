import sys
import os
import time

from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox, QLineEdit
from PyQt6.QtCore import QTimer

from async_obd_manager import AsyncOBDManager
from mock_obd_manager import MockOBDManager
from thermo_diagnostics import ThermodynamicDiagnosticEngine
from rag_knowledge_engine import LocalServiceManualRAG
from gui_dashboard import PMMPProDash
from data_logger import SessionDataLogger
from utils.config import init_config, get_config
from utils.logger import get_logger

logger = get_logger(__name__)

def authenticate_gatekeeper(shop_password: str = "pmmp", max_attempts: int = 3) -> bool:
    """
    Workshop Gatekeeper modal authentication dialog.
    Must be called with a live QApplication before launching main workspace.
    """
    app = QApplication.instance()
    owns_app = False
    if not app:
        app = QApplication(sys.argv)
        owns_app = True

    authenticated = False
    for attempt in range(max_attempts):
        password, ok = QInputDialog.getText(
            None,
            "PMMP Pro-Dash Security",
            "Enter Workshop Terminal Password:",
            QLineEdit.EchoMode.Password
        )
        if not ok:
            return False

        if password == shop_password:
            authenticated = True
            break
        else:
            remaining = max_attempts - 1 - attempt
            if remaining > 0:
                QMessageBox.warning(
                    None,
                    "Access Denied",
                    f"Incorrect password. {remaining} attempts remaining."
                )

    if not authenticated:
        QMessageBox.critical(
            None,
            "Locked Out",
            "Too many failed attempts. Terminating session."
        )

    if owns_app:
        app.processEvents()

    return authenticated

class PMMPController:
    def __init__(self, use_mock: bool = False):
        # Initialize configuration
        env = os.getenv('PMMP_ENV', 'production')
        self.config = init_config(env)
        logger.info(f"PMMP Pro-G4 initialized in {self.config.env} mode")
        
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.gui = PMMPProDash()
        self.use_mock = use_mock
        
        # Wire up console input handler
        self.gui.console_input.returnPressed.connect(self.handle_console_command)
        
        # Initialize Async Session Logger
        self.data_logger = SessionDataLogger()
        
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
            logger.info("OBD Manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize OBD Manager: {e}")
            self.obd_mgr = None
        
        try:
            engine_config = self.config.get_section('engine')
            self.physics_engine = ThermodynamicDiagnosticEngine(
                displacement_liters=engine_config.get('displacement_liters', 2.0)
            )
            logger.info(f"Physics Engine initialized: {engine_config.get('displacement_liters', 2.0)}L")
        except Exception as e:
            logger.error(f"Failed to initialize Physics Engine: {e}")
            self.physics_engine = None
        
        try:
            rag_config = self.config.get_section('rag')
            self.rag_engine = LocalServiceManualRAG(
                db_path=rag_config.get('manual_db_path', './service_manuals_index.json')
            )
            logger.info("RAG Knowledge Engine initialized")
        except Exception as e:
            logger.error(f"Failed to initialize RAG Engine: {e}")
            self.rag_engine = None
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.system_tick)
        
        self.diagnostic_cycle_counter = 0
        self.active_dtcs = []
        self.last_dtc_analysis = {}

    def start(self):
        """Start the application and background workers."""
        try:
            self.data_logger.start()

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
            self.data_logger.stop()
            if self.obd_mgr:
                self.obd_mgr.stop_stream()
            logger.info("Application shutting down")
            sys.exit(exit_code if 'exit_code' in locals() and exit_code else 0)
    
    def system_tick(self):
        """Periodic real-time data pipeline tick (VE calculation, trim evaluation, UI refresh, async logging)."""
        try:
            self.diagnostic_cycle_counter += 1
            
            # STEP 1: Telemetry snapshot acquisition
            telemetry = self._get_telemetry()
            
            # STEP 2: Physics computation (VE and fuel trims)
            if self.physics_engine:
                ve = self.physics_engine.calculate_volumetric_efficiency(telemetry)
                telemetry["VE"] = round(ve * 100.0, 1)
                self.physics_engine.evaluate_fuel_trim_matrix(telemetry)
            
            # Non-blocking async queue logging
            self.data_logger.log_telemetry(telemetry)
            
            # STEP 3: DTC polling cycle (every 100 ticks)
            if self.diagnostic_cycle_counter >= 100:
                self.active_dtcs = self.obd_mgr.query_active_dtcs() if self.obd_mgr else []
                self.diagnostic_cycle_counter = 0

            # STEP 4: Causal root-cause analysis
            dtc_analysis = self._analyze_dtcs(self.active_dtcs) if self.physics_engine else {}
            
            # STEP 5: RAG service manual contextualization
            rag_data = self._get_rag_data(dtc_analysis) if self.rag_engine else {}
            
            # STEP 6: Update GUI
            if self.gui:
                self.gui.update_ui(telemetry, dtc_analysis, rag_data)
            
            self.last_dtc_analysis = dtc_analysis
            
        except Exception as e:
            logger.error(f"Error in system tick: {e}")
    
    def _get_telemetry(self) -> dict:
        """Get current vehicle telemetry snapshot from OBD manager."""
        if not self.obd_mgr:
            return {
                "RPM": 0, "LOAD": 0.0, "STFT": 0.0,
                "LTFT": 0.0, "COOLANT": 0, "MAF": 0.0,
                "MAP": 101.3, "IAT": 25.0, "O2_V": 0.0, "VE": 0.0
            }
        
        try:
            if hasattr(self.obd_mgr, 'get_snapshot'):
                return self.obd_mgr.get_snapshot()
            elif hasattr(self.obd_mgr, 'get_telemetry'):
                return self.obd_mgr.get_telemetry()
            else:
                return getattr(self.obd_mgr, 'telemetry_cache', {}).copy()
        except Exception as e:
            logger.debug(f"Error getting telemetry: {e}")
            return {}
    
    def _analyze_dtcs(self, active_dtcs: list) -> dict:
        """Use physics engine to analyze DTCs."""
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
        """Get RAG procedures for root cause codes."""
        if not self.rag_engine:
            return {}
        
        root_causes = dtc_analysis.get('root_causes', [])
        if not root_causes:
            return {}
        
        try:
            primary_code = root_causes[0]
            return self.rag_engine.query_diagnostic_procedure(primary_code)
        except Exception as e:
            logger.error(f"Error getting RAG data: {e}")
            return {}
    
    def handle_console_command(self):
        """Unified REPL command processor supporting built-in and UDS reverse-engineering commands."""
        try:
            cmd = self.gui.console_input.text().strip()
            self.gui.console_input.clear()
            
            if not cmd:
                return
            
            logger.debug(f"Console command received: {cmd}")
            self.gui.console_output.append(f">> {cmd}")
            
            parts = cmd.split()
            upper_cmd = parts[0].upper()
            
            # Built-in High Level Commands
            if upper_cmd == "HELP":
                self._show_help()
            elif upper_cmd == "CLEAR":
                self.gui.console_output.clear()
            elif upper_cmd == "STATUS":
                self._show_status()
            elif upper_cmd == "ATZ":
                self._reset_device()
            elif upper_cmd == "DTC":
                self._read_dtc()
            elif upper_cmd == "LIVE":
                self._toggle_live_data()
            elif upper_cmd in ("EXIT", "QUIT"):
                self.app.quit()
            # Advanced Protocol / UDS / Hardware Commands
            elif upper_cmd in ("HEADER", "RAW", "UDS_READ", "UDS_CTRL", "SCAN"):
                self._handle_hardware_protocol_command(upper_cmd, parts, cmd)
            else:
                self.gui.console_output.append(f"❌ Unknown command: {cmd}. Type HELP for available commands.")
        except Exception as e:
            logger.error(f"Error handling console command: {e}")
            self.gui.console_output.append(f"❌ Error: {e}")
    
    def _handle_hardware_protocol_command(self, upper_cmd: str, parts: list, full_cmd: str):
        """Executes raw UDS/CAN protocol transactions via the ELM/STN interface."""
        if not self.obd_mgr or not hasattr(self.obd_mgr, 'connection') or not self.obd_mgr.connection or not self.obd_mgr.connection.interface:
            self.gui.console_output.append("❌ Error: Hardware interface not active. Run connected to physical OBD device.")
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
                payload = f"22 {did}"
                resp = interface.send(payload)
                self.gui.console_output.append(f"UDS Read [{did}] -> {resp}")
                
            elif upper_cmd == "UDS_CTRL" and len(parts) > 2:
                did = parts[1]
                param = parts[2]
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
                    resp = interface.send("3E 00")
                    if resp and "NO DATA" not in str(resp) and "Error" not in str(resp) and "?" not in str(resp):
                        active_nodes.append(id_hex)
                        self.gui.console_output.append(f"  [+] Active Node Found: 0x{id_hex} -> {resp}")
                
                interface.send("AT SH 7E0")
                self.gui.console_output.append(f"Scan complete. Found {len(active_nodes)} responding modules.")
            else:
                resp = interface.send(full_cmd)
                self.gui.console_output.append(str(resp))
        except Exception as e:
            self.gui.console_output.append(f"Hardware command execution failed: {e}")

    def _show_help(self):
        """Display available commands."""
        help_text = """
╔════════════════════════════════════════════════════════╗
║           PMMP Pro-G4 Workstation Terminal            ║
╚════════════════════════════════════════════════════════╝

Diagnostic Commands:
  HELP               - Display command reference
  STATUS             - Show system connectivity & pipeline status
  LIVE               - Display current telemetry metrics snapshot
  DTC                - Read active DTCs & run causal dependency graph
  CLEAR              - Clear console output window
  ATZ                - Send ELM reset & clear fault memory
  EXIT/QUIT          - Terminate session

Advanced Protocol & UDS:
  HEADER <can_id>    - Set CAN transmit header (e.g. HEADER 726)
  RAW <hex>          - Transmit raw hex payload to vehicle bus
  SCAN               - Sweep standard ECU/BCM addresses (Tester Present 3E 00)
  UDS_READ <did>     - Read Data By Identifier (Service 22, e.g. UDS_READ F190)
  UDS_CTRL <did> <v> - Input/Output Control (Service 2F, e.g. UDS_CTRL 0301 03)
"""
        self.gui.console_output.append(help_text)

    def _reset_device(self):
        """Reset OBD device and clear DTCs."""
        try:
            if self.obd_mgr:
                self.gui.console_output.append("🔄 Resetting device and clearing DTCs...")
                if hasattr(self.obd_mgr, 'clear_dtcs'):
                    self.obd_mgr.clear_dtcs()
                    self.gui.console_output.append("✅ DTCs cleared successfully")
                else:
                    self.gui.console_output.append("✅ Device reset command sent")
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
                return
            
            self.gui.console_output.append(f"📋 Active DTCs ({len(active_dtcs)}):")
            for code in active_dtcs:
                self.gui.console_output.append(f"   • {code}")
            
            if self.last_dtc_analysis:
                roots = self.last_dtc_analysis.get('root_causes', [])
                suppressed = self.last_dtc_analysis.get('suppressed_symptom_codes', [])
                
                if roots:
                    self.gui.console_output.append(f"\n🔍 Primary Root Causes:")
                    for code in roots:
                        self.gui.console_output.append(f"   • {code}")
                if suppressed:
                    self.gui.console_output.append(f"\n🔗 Suppressed Symptom Codes:")
                    for code in suppressed:
                        self.gui.console_output.append(f"   • {code}")
        except Exception as e:
            logger.error(f"Error reading DTCs: {e}")
            self.gui.console_output.append(f"❌ Error: {e}")

    def _toggle_live_data(self):
        """Display snapshot of telemetry stream."""
        try:
            self.gui.console_output.append("📡 Live Telemetry Snapshot:")
            telemetry = self._get_telemetry()
            if telemetry:
                self.gui.console_output.append(f"   RPM:     {telemetry.get('RPM', 0):.0f} RPM")
                self.gui.console_output.append(f"   LOAD:    {telemetry.get('LOAD', 0):.1f} %")
                self.gui.console_output.append(f"   MAF:     {telemetry.get('MAF', 0):.1f} g/s")
                self.gui.console_output.append(f"   VE:      {telemetry.get('VE', 0.0):.1f} %")
                self.gui.console_output.append(f"   STFT:    {telemetry.get('STFT', 0):.1f} %")
                self.gui.console_output.append(f"   LTFT:    {telemetry.get('LTFT', 0):.1f} %")
                self.gui.console_output.append(f"   COOLANT: {telemetry.get('COOLANT', 0):.0f} °C")
                self.gui.console_output.append(f"   O2_V:    {telemetry.get('O2_V', 0):.2f} V")
            else:
                self.gui.console_output.append("   (No telemetry available)")
        except Exception as e:
            logger.error(f"Error displaying live data: {e}")
            self.gui.console_output.append(f"❌ Error: {e}")

    def _show_status(self):
        """Display system status."""
        try:
            mode = "MOCK" if self.use_mock else "HARDWARE"
            env = self.config.env.upper()
            is_connected = bool(self.obd_mgr and getattr(self.obd_mgr, 'is_running', False))
            
            status_text = f"""
╔════════════════════════════════════════════════════════╗
║              PMMP Pro-G4 System Status                 ║
╚════════════════════════════════════════════════════════╝
Environment:  {env}
Mode:         {mode}
OBD Status:   {'Streaming' if is_connected else 'Idle/Offline'}
Active DTCs:  {len(self.active_dtcs)}
Cycle Count:  {self.diagnostic_cycle_counter}
Log File:     {self.data_logger.current_filepath or 'None'}
"""
            self.gui.console_output.append(status_text)
        except Exception as e:
            logger.error(f"Error showing status: {e}")
            self.gui.console_output.append(f"❌ Error: {e}")
