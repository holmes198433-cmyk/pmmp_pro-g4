# PMMP Pro-G4 - Vehicle Diagnostics System

**LOOSE NUTZ GARAGE // PMMP PRO-DASH v3.0-PHYSICS**

A professional vehicle diagnostic system using Retrieval-Augmented Generation (RAG), on-board diagnostics (OBD-II), and thermodynamic physics analysis.

## Features

- 🚗 **Real-time OBD-II Data Streaming** - Connect to vehicle diagnostic port
- 🧠 **RAG-Powered Knowledge Base** - Service manual lookup for diagnostic codes
- 🔬 **Physics Engine** - Thermodynamic diagnostics analysis
- 📊 **Professional GUI Dashboard** - PyQt6-based interface with live telemetry
- 🔧 **Console/REPL Interface** - Command-line interface for advanced operations
- ⚙️ **Configuration System** - Environment-based config (dev, production)
- 📝 **Comprehensive Logging** - Full logging with rotation for production

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Choose Your Environment

Set the environment (default is production):

```bash
export PMMP_ENV=development  # or 'production'
python main.py
```

### 3. Run the Application

```bash
python main.py
```

The GUI will start with the dashboard. Use the console at the bottom for commands.

## Configuration

Configuration is managed through JSON files in the `config/` directory:

- `config/default.json` - Base configuration (production defaults)
- `config/development.json` - Development overrides
- Environment variables prefixed with `PMMP_` override config files

### Configuration Structure

```json
{
  "app": { "name": "PMMP Pro-G4", "version": "1.0.0", "mode": "production" },
  "obd": { "port": "/dev/...", "fast_init": true, "baudrate": 115200, "timeout": 10 },
  "engine": { "displacement_liters": 2.0, "fuel_type": "gasoline" },
  "gui": { "window_width": 1200, "window_height": 800, "theme": "dark", "refresh_rate_ms": 50 },
  "rag": { "manual_db_path": "./service_manuals", "use_remote": false },
  "logging": { "level": "INFO", "log_file": "./logs/pmmp.log", "max_log_size_mb": 10 },
  "diagnostics": { "enable_physics_analysis": true, "enable_rag_lookup": true }
}
```

### Environment Variables

Override config values using `PMMP_SECTION_KEY` format:

```bash
export PMMP_OBD_PORT="/dev/ttyUSB0"
export PMMP_LOGGING_LEVEL="DEBUG"
export PMMP_OBD_FAST_INIT="false"
python main.py
```

## Console Commands

Available commands in the GUI console:

| Command | Description |
|---------|-------------|
| `HELP` | Show available commands |
| `ATZ` | Reset OBD device |
| `DTC` | Read diagnostic trouble codes |
| `LIVE` | Toggle live data streaming |
| `EXIT` / `QUIT` | Exit application |

## Project Structure

```
pmmp_pro-g4/
├── config/                      # Configuration files
│   ├── default.json            # Production config
│   └── development.json        # Development overrides
├── utils/                       # Utility modules
│   ├── config.py               # Configuration loader
│   └── logger.py               # Logging setup
├── pmmp_controller.py          # Main controller
├── async_obd_manager.py        # OBD hardware manager
├── thermo_diagnostics.py       # Physics engine
├── rag_diagnostics_engine.py   # Knowledge base
├── gui_dashboard.py            # PyQt6 UI
├── rag_knowledge_engine.py     # RAG implementation
├── main.py                     # Entry point
├── requirements.txt            # Dependencies
├── setup.py                    # Installation script
└── PRODUCTION_ROADMAP.md       # Detailed roadmap
```

## Development

### Running in Development Mode

```bash
export PMMP_ENV=development
python main.py
```

Development mode:
- Enables DEBUG logging
- Uses mock OBD device
- Disables result caching

### Logging

Logs are written to `./logs/pmmp.log` with automatic rotation.

Monitor logs in real-time:

```bash
tail -f logs/pmmp.log
```

## Hardware Setup

### Required Hardware

- **OBD-II Adapter**: ScanTool.net LLC OBDLink EX or compatible
- **Vehicle**: 2008+ with OBD-II port

### Serial Port Configuration

Update the serial port in `config/production.json`:

```bash
# Linux/Mac
ls /dev/tty.* /dev/cu.*

# Windows
# COM ports in Device Manager
```

## Troubleshooting

### Hardware Not Detected

The system falls back to **mock mode** if hardware fails:

```
⚠️  WARNING: Hardware not detected. Running in mock mode.
```

This allows testing without a vehicle connected.

### Configuration Issues

Check logs for configuration errors:

```bash
tail -f logs/pmmp.log | grep -i config
```

### Import Errors

Ensure all dependencies are installed:

```bash
pip install -r requirements.txt --upgrade
```

## Production Deployment

### Installation

```bash
pip install -e .
pmmp-pro-g4  # Runs the application
```

### Docker Support (Coming Soon)

```bash
docker build -t pmmp-pro-g4 .
docker run -p 5000:5000 pmmp-pro-g4
```

### Performance Considerations

- **GUI Refresh Rate**: Set `gui.refresh_rate_ms` in config (default 50ms = 20 Hz)
- **Logging Level**: Set to `WARNING` or `ERROR` in production
- **Cache**: Enable `diagnostics.cache_results` for faster lookups

## API Reference

### PMMPController

```python
from pmmp_controller import PMMPController

controller = PMMPController()
controller.start()  # Starts the application
```

### Accessing Config

```python
from utils.config import get_config

config = get_config()
obd_port = config.get('obd.port')
all_settings = config.to_dict()
```

### Accessing Logger

```python
from utils.logger import get_logger

logger = get_logger(__name__)
logger.info("Application started")
logger.error("Error occurred", exc_info=True)
```

## Contributing

When adding new features:

1. Add configuration to `config/default.json`
2. Add logging throughout the code
3. Use the config system for all settings
4. Update this README

## License

Proprietary - Loose Nutz Garage

## Support

For issues and feature requests, check the [PRODUCTION_ROADMAP.md](PRODUCTION_ROADMAP.md).

---

**Last Updated**: 2024-08-13  
**Version**: 1.0.0  
**Status**: Beta (Production Ready)
