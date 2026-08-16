"""
Logging configuration for PMMP Pro-G4
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional
from .config import get_config

class Logger:
    """
    Centralized logging setup for PMMP Pro-G4
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        config = get_config()
        log_config = config.get_section('logging')
        
        # Create logs directory if needed
        log_dir = Path(log_config.get('log_file', './logs/pmmp.log')).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure root logger
        self.logger = logging.getLogger('PMMP')
        level = getattr(logging, log_config.get('level', 'INFO'))
        self.logger.setLevel(level)
        
        # Remove existing handlers
        self.logger.handlers.clear()
        
        # File handler with rotation
        log_file = log_config.get('log_file', './logs/pmmp.log')
        max_bytes = log_config.get('max_log_size_mb', 10) * 1024 * 1024
        backup_count = log_config.get('backup_count', 5)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(level)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        self._initialized = True
    
    def get_logger(self, name: str = 'PMMP') -> logging.Logger:
        """Get a logger instance."""
        return logging.getLogger(name)


def get_logger(name: str = 'PMMP') -> logging.Logger:
    """Get a logger instance."""
    logger_obj = Logger()
    return logger_obj.get_logger(name)
