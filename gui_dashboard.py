import pyqtgraph as pg
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QFrame, QMessageBox)
from PyQt6.QtGui import QFont

class PMMPProDash(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LOOSE NUTZ GARAGE // PMMP PRO-DASH")
        self.resize(1200, 800)
        self.setStyleSheet("background-color: #020617; color: #cbd5e1;")
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(20)
        
        self._setup_console()
        self._setup_header()
        self._setup_metrics()
        self._setup_graphs()
        self._setup_diagnostics()

        self.rpm_data = [0] * 100
        
    def _setup_console(self):
        console_frame = QFrame()
        console_frame.setStyleSheet("background-color: #0f172a; border: 1px solid #1e293b; border-radius: 10px;")
        layout = QVBoxLayout(console_frame)
        
        title = QLabel("SYSTEM TERMINAL // REPL COMMAND CONSOLE")
        title.setFont(QFont("Courier", 10, QFont.Weight.Bold))
        title.setStyleSheet("border: none; color: #38bdf8;")
        layout.addWidget(title)

        # Output log display
        self.console_output = pg.QtWidgets.QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setStyleSheet("background-color: #020617; color: #34d399; border: 1px solid #1e293b; font-family: Courier; font-size: 11pt;")
        self.console_output.append(">> PMMP Core Terminal Initialized. Type commands below.")
        layout.addWidget(self.console_output)

        # Input line
        self.console_input = pg.QtWidgets.QLineEdit()
        self.console_input.setStyleSheet("background-color: #020617; color: #f8fafc; border: 1px solid #334155; padding: 6px; font-family: Courier; font-size: 11pt;")
        self.console_input.setPlaceholderText("Enter command (e.g., ATZ, HELP, DTC)...")
        layout.addWidget(self.console_input)
        
        self.main_layout.addWidget(console_frame)
        
    def _setup_header(self):
        header = QFrame()
        header.setStyleSheet("background-color: #0f172a; border: 1px solid #1e293b; border-radius: 10px;")
        layout = QHBoxLayout(header)
        
        title = QLabel("LOOSE NUTZ GARAGE // PMMP PRO-DASH v3.0-PHYSICS")
        title.setFont(QFont("Courier", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #22d3ee; border: none;")
        
        subtitle = QLabel("ISO 15765-4 CAN // OBDLink EX 1M Baud")
        subtitle.setFont(QFont("Courier", 10))
        subtitle.setStyleSheet("color: #10b981; border: none;")
        
        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(subtitle)
        self.main_layout.addWidget(header)

    def _setup_metrics(self):
        metrics_layout = QHBoxLayout()
        self.lbl_rpm = self._create_metric_card(metrics_layout, "ENGINE SPEED", "0 RPM", "#22d3ee")
        self.lbl_load = self._create_metric_card(metrics_layout, "CALC LOAD", "0.0 %", "#10b981")
        self.lbl_trim = self._create_metric_card(metrics_layout, "TOTAL TRIM", "0.0 %", "#c084fc")
        self.lbl_temp = self._create_metric_card(metrics_layout, "COOLANT", "0 °C", "#fbbf24")
        self.main_layout.addLayout(metrics_layout)

    def _create_metric_card(self, parent_layout, label_text, value_text, color):
        card = QFrame()
        card.setStyleSheet(f"background-color: #0f172a; border: 1px solid {color}; border-radius: 10px;")
        layout = QVBoxLayout(card)
        
        lbl = QLabel(label_text)
        lbl.setFont(QFont("Courier", 10, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #64748b; border: none;")
        
        val = QLabel(value_text)
        val.setFont(QFont("Courier", 20, QFont.Weight.Bold))
        val.setStyleSheet(f"color: {color}; border: none;")
        
        layout.addWidget(lbl)
        layout.addWidget(val)
        parent_layout.addWidget(card)
        return val

    def _setup_graphs(self):
        graph_frame = QFrame()
        graph_frame.setStyleSheet("background-color: #0f172a; border: 1px solid #1e293b; border-radius: 10px;")
        layout = QVBoxLayout(graph_frame)
        
        title = QLabel("DYNAMIC TELEMETRY STREAM (48 Hz Target)")
        title.setFont(QFont("Courier", 12, QFont.Weight.Bold))
        title.setStyleSheet("border: none; color: #e2e8f0;")
        layout.addWidget(title)

        pg.setConfigOptions(antialias=True)
        self.plot_widget = pg.PlotWidget(background='#0f172a')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setYRange(0, 7000) 
        
        self.rpm_curve = self.plot_widget.plot(pen=pg.mkPen('#22d3ee', width=2), name="RPM")
        layout.addWidget(self.plot_widget)
        self.main_layout.addWidget(graph_frame)

    def _setup_diagnostics(self):
        diag_layout = QHBoxLayout()
        
        root_frame = QFrame()
        root_frame.setStyleSheet("background-color: #0f172a; border: 1px solid #1e293b; border-radius: 10px;")
        root_layout = QVBoxLayout(root_frame)
        self.lbl_dtc = QLabel("CAUSAL GRAPH: AWAITING DATA...")
        self.lbl_dtc.setFont(QFont("Courier", 10))
        self.lbl_dtc.setStyleSheet("color: #f87171; border: none;")
        root_layout.addWidget(self.lbl_dtc)
        
        rag_frame = QFrame()
        rag_frame.setStyleSheet("background-color: #0f172a; border: 1px solid #1e293b; border-radius: 10px;")
        rag_layout = QVBoxLayout(rag_frame)
        self.lbl_rag = QLabel("RAG KNOWLEDGE BASE: IDLE")
        self.lbl_rag.setFont(QFont("Courier", 10))
        self.lbl_rag.setStyleSheet("color: #fbbf24; border: none;")
        rag_layout.addWidget(self.lbl_rag)
        
        diag_layout.addWidget(root_frame)
        diag_layout.addWidget(rag_frame)
        self.main_layout.addLayout(diag_layout)

    def update_ui(self, telemetry, dtc_analysis, rag_data):
        rpm = telemetry.get("RPM", 0)
        self.lbl_rpm.setText(f"{int(rpm)} RPM")
        self.lbl_load.setText(f"{telemetry.get('LOAD', 0):.1f} %")
        trim = telemetry.get("STFT", 0) + telemetry.get("LTFT", 0)
        self.lbl_trim.setText(f"{trim:.1f} %")
        self.lbl_temp.setText(f"{telemetry.get('COOLANT', 0)} °C")

        self.rpm_data[:-1] = self.rpm_data[1:]
        self.rpm_data[-1] = rpm
        self.rpm_curve.setData(self.rpm_data)

        if dtc_analysis.get("root_causes"):
            root = ", ".join(dtc_analysis['root_causes'])
            supp = ", ".join(dtc_analysis['suppressed_symptom_codes'])
            self.lbl_dtc.setText(f"PRIMARY ROOT: {root}\nSUPPRESSED: {supp}")
        else:
            self.lbl_dtc.setText("SYSTEM HEALTHY: NO ACTIVE DTCs")

        if rag_data:
            code = rag_data.get('code', '')
            steps = "\n".join(rag_data.get('inspection_steps', []))
            self.lbl_rag.setText(f"PROCEDURE {code}:\n{steps}")
    
    def show_error(self, message: str):
        """Display error dialog."""
        QMessageBox.critical(self, "Error", message)
