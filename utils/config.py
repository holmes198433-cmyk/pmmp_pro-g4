"""
Configuration management for PMMP Pro-G4
Loads configuration from JSON files based on environment
"""

import json
import os
from pathlib import Path
from typing import Dict, Any

class Config:
    """
    Configuration loader that merges base config with environment-specific overrides.
    """
    
    def __init__(self, env: str = None):
        """
        Initialize config loader.
        
        Args:
            env: Environment name (production, development, testing)
                 Defaults to ENV variable or 'production'
        """
        self.env = env or os.getenv('PMMP_ENV', 'production')
        self.config_dir = Path(__file__).parent.parent / 'config'
        self.data = {}
        self._load_config()
    
    def _load_config(self):
        """Load base config and environment-specific overrides."""
        # Load default config
        default_config_path = self.config_dir / 'default.json'
        if default_config_path.exists():
            with open(default_config_path, 'r') as f:
                self.data = json.load(f)
        else:
            raise FileNotFoundError(f"Default config not found: {default_config_path}")
        
        # Load environment-specific config
        env_config_path = self.config_dir / f'{self.env}.json'
        if env_config_path.exists():
            with open(env_config_path, 'r') as f:
                env_config = json.load(f)
                self._merge_config(self.data, env_config)
        
        # Load from environment variables (override config files)
        self._load_env_overrides()
    
    def _merge_config(self, base: Dict, override: Dict) -> None:
        """Recursively merge override config into base config."""
        for key, value in override.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def _load_env_overrides(self):
        """Load overrides from environment variables (PMMP_* pattern)."""
        for key, value in os.environ.items():
            if key.startswith('PMMP_'):
                # Convert PMMP_OBD_PORT to obd.port
                parts = key[5:].lower().split('_')
                self._set_nested_value(self.data, parts, value)
    
    def _set_nested_value(self, obj: Dict, keys: list, value: str) -> None:
        """Set a nested dictionary value."""
        for key in keys[:-1]:
            if key not in obj:
                obj[key] = {}
            obj = obj[key]
        obj[keys[-1]] = value
    
    def get(self, key: str, default=None) -> Any:
        """
        Get config value using dot notation.
        
        Args:
            key: Key path (e.g., 'obd.port', 'gui.window_width')
            default: Default value if key not found
        
        Returns:
            Config value or default
        """
        keys = key.split('.')
        value = self.data
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_section(self, section: str) -> Dict:
        """Get entire config section."""
        return self.data.get(section, {})
    
    def to_dict(self) -> Dict:
        """Get entire config as dictionary."""
        return self.data.copy()
    
    def __repr__(self):
        return f"Config(env={self.env}, keys={list(self.data.keys())})"


# Global config instance
_config = None

def init_config(env: str = None) -> Config:
    """Initialize global config."""
    global _config
    _config = Config(env)
    return _config

def get_config() -> Config:
    """Get global config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
