import os
import csv
import time
import queue
import threading
from datetime import datetime
from typing import Dict, Any, Optional

from utils.logger import get_logger

logger = get_logger(__name__)

class SessionDataLogger:
    """
    Thread-safe, queue-based CSV session logger for high-frequency OBD PID telemetry.
    Flushes records to disk asynchronously to prevent blocking the UI loop.
    """
    def __init__(self, output_dir: str = "session_logs", max_queue_size: int = 5000):
        self.output_dir = output_dir
        self.max_queue_size = max_queue_size
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._fieldnames = [
            "timestamp", "RPM", "LOAD", "MAF", "MAP", "IAT", 
            "STFT", "LTFT", "COOLANT", "O2_V", "VE"
        ]
        self.current_filepath: Optional[str] = None

    def start(self) -> None:
        """Start the background worker thread for writing log records."""
        os.makedirs(self.output_dir, exist_ok=True)
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_filepath = os.path.join(self.output_dir, f"session_{session_id}.csv")
        
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._writer_loop, 
            name="SessionDataLoggerThread", 
            daemon=True
        )
        self._worker_thread.start()
        logger.info(f"Session data logger started: {self.current_filepath}")

    def log_telemetry(self, telemetry: Dict[str, Any]) -> None:
        """Enqueue a telemetry snapshot non-blockingly."""
        if not self._worker_thread or not self._worker_thread.is_alive():
            return
            
        record = {
            "timestamp": time.time(),
            "RPM": telemetry.get("RPM", 0),
            "LOAD": telemetry.get("LOAD", 0.0),
            "MAF": telemetry.get("MAF", 0.0),
            "MAP": telemetry.get("MAP", 101.3),
            "IAT": telemetry.get("IAT", 25.0),
            "STFT": telemetry.get("STFT", 0.0),
            "LTFT": telemetry.get("LTFT", 0.0),
            "COOLANT": telemetry.get("COOLANT", 0),
            "O2_V": telemetry.get("O2_V", 0.0),
            "VE": telemetry.get("VE", 0.0)
        }
        
        try:
            self._queue.put_nowait(record)
        except queue.Full:
            logger.warning("Telemetry logging queue full. Dropped sample.")

    def _writer_loop(self) -> None:
        """Background loop reading from queue and appending to CSV file."""
        if not self.current_filepath:
            return

        with open(self.current_filepath, mode="w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=self._fieldnames)
            writer.writeheader()
            csv_file.flush()

            while not self._stop_event.is_set() or not self._queue.empty():
                try:
                    record = self._queue.get(timeout=0.2)
                    writer.writerow(record)
                    self._queue.task_done()
                    csv_file.flush()
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Error writing telemetry record to CSV: {e}")

    def stop(self) -> None:
        """Flush remaining queue items and terminate worker thread."""
        if self._worker_thread and self._worker_thread.is_alive():
            self._stop_event.set()
            self._worker_thread.join(timeout=2.0)
            logger.info("Session data logger stopped.")
