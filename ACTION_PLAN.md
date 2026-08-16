# PMMP Pro-G4: Complete Action Plan

## 🎯 Your Next Steps (5-Step Path)

You want to: **Test → Simulate → Debug → Setup Hardware → Deploy**

---

## STEP 1️⃣: RUN AUTOMATED TESTS (5 minutes)

### Why: Verify all components are working correctly

### Commands:
```bash
cd ~/Desktop/Prog.-Devs./PMMP_Pro-G/pmmp_pro-g4

# Option A: Run tests via main.py
python3 main.py --test

# Option B: Run tests directly
cd tests && python3 test_pmmp.py

# Option C: Run with verbose output
python3 -m unittest discover -s tests -v
```

### Expected Output:
```
test_config_loads ... ok
test_config_get_simple ... ok
test_config_get_nested ... ok
test_config_get_section ... ok
test_initialization ... ok
test_get_telemetry ... ok
test_start_stop_stream ... ok
test_dtc_injection ... ok
test_clear_dtcs ... ok
test_volumetric_efficiency ... ok
test_fuel_trim_analysis ... ok
test_dtc_isolation ... ok
test_query_known_code ... ok
test_query_unknown_code ... ok
test_pinout_specs ... ok
test_mock_to_physics_to_rag_pipeline ... ok

Ran 16 tests in 19.6s
OK
```

### What It Tests:
- ✅ Configuration system loads correctly
- ✅ Mock OBD manager generates realistic data
- ✅ Physics engine analyzes DTCs
- ✅ RAG engine retrieves procedures
- ✅ Full data pipeline works end-to-end

**👉 DO THIS FIRST - Takes 30 seconds**

---

## STEP 2️⃣: RUN SIMULATION (10 minutes)

### Why: See the complete system in action without GUI

### Commands:
```bash
cd ~/Desktop/Prog.-Devs./PMMP_Pro-G/pmmp_pro-g4

# Normal simulation (recommended)
python3 simulate.py normal

# Demo mode (fast)
python3 simulate.py demo

# Get help
python3 simulate.py help
```

### What You'll See:
```
╔════════════════════════════════════════════════════╗
║        PMMP Pro-G4 Headless Simulation            ║
╚════════════════════════════════════════════════════╝

[Cycle  10] RPM: 1245 | LOAD: 8.5% | MAF: 5.2 g/s | STFT: -2.1% | LTFT: 1.8%
[Cycle  20] RPM: 2180 | LOAD: 22.3% | MAF: 8.7 g/s | STFT: 1.5% | LTFT: -0.8%
...
[Cycle 150] P0171 DETECTED (System Too Lean)

📋 Analysis:
  Root Cause: MAF sensor drift (measuring low)
  Symptom Chain: P0171 → P0134 (MAF inactive)
  
🔧 Procedure:
  1. Inspect MAF sensor for contamination
  2. Clean with MAF-safe cleaner
  3. Check for air leaks post-MAF
```

### What It Validates:
- ✅ OBD manager generates 150 cycles of realistic data
- ✅ Physics engine analyzes each cycle
- ✅ Fault injection (P0171) works correctly
- ✅ Root cause analysis displays properly
- ✅ End-to-end pipeline functional

**👉 DO THIS SECOND - Takes 1 minute to run, shows everything working**

---

## STEP 3️⃣: RUN GUI WITH MOCK OBD (15 minutes)

### Why: See the professional dashboard interface

### Command:
```bash
cd ~/Desktop/Prog.-Devs./PMMP_Pro-G/pmmp_pro-g4
python3 main.py --mock
```

### What Appears:
```
┌─────────────────────────────────────────────┐
│         PMMP Pro-G4 Diagnostics GUI         │
├─────────────────────────────────────────────┤
│                                             │
│  📊 Metrics:  RPM: 1245   LOAD: 8.5%      │
│               MAF: 5.2    COOLANT: 92°C    │
│               STFT: -2.1% LTFT: 1.8%       │
│                                             │
│  📈 Real-time RPM Graph                    │
│                                             │
│  🚨 DTCs: None                              │
│                                             │
│  > _                                        │
│  Console (type: HELP, DTC, LIVE, etc)      │
│                                             │
└─────────────────────────────────────────────┘
```

### Available Commands in Console:
| Command | Example | Result |
|---------|---------|--------|
| HELP | `HELP` | Show all commands |
| LIVE | `LIVE` | Display current telemetry |
| DTC | `DTC` | Show active diagnostic codes |
| STATUS | `STATUS` | System status & statistics |
| ATZ | `ATZ` | Reset device & clear codes |
| CLEAR | `CLEAR` | Clear DTCs |
| EXIT | `EXIT` | Close application |

### Try These Commands:
```
>> HELP          # See all commands
>> LIVE          # View telemetry streaming
>> DTC           # Check for codes (should see P0171 after ~30s)
>> STATUS        # See system info
>> EXIT          # Close when done
```

**👉 DO THIS THIRD - Takes 2 minutes to see GUI, try commands, exit**

---

## STEP 4️⃣: SETUP FOR REAL HARDWARE (30 minutes)

### Prerequisites Checklist:
- [ ] OBD-II vehicle (2006+)
- [ ] OBD-II Bluetooth/USB adapter
- [ ] Laptop with Python 3.8+
- [ ] PyQt6 installed (`pip install -r requirements.txt`)

### Hardware Setup Steps:

#### 4a. Identify Your OBD Device

Plug in OBD adapter and find its port:

**Linux:**
```bash
# List all serial devices
ls /dev/tty*
ls /dev/ttyUSB*        # USB adapters
ls /dev/rfcomm*        # Bluetooth adapters

# Result might be: /dev/ttyUSB0
```

**macOS:**
```bash
ls /dev/tty.usbserial*
ls /dev/tty.SLAB_USBtoUART*
```

**Windows:**
```cmd
# Device Manager → Ports (COM & LPT)
# Look for: COM3, COM4, etc
```

#### 4b. Update Production Config

Edit [config/production.json](config/production.json):

```json
{
  "app": {
    "environment": "production"
  },
  "obd": {
    "port": "/dev/ttyUSB0",        # <-- CHANGE THIS
    "baudrate": 115200,
    "fast_init": true,
    "timeout": 10,
    "fallback_mode": "error"       # Fail if no connection
  }
}
```

Replace `/dev/ttyUSB0` with YOUR port from step 4a.

#### 4c. Test Hardware Connection

```bash
cd ~/Desktop/Prog.-Devs./PMMP_Pro-G/pmmp_pro-g4

# Start with mock mode first (verify GUI works)
python3 main.py --mock

# Then try production (with real OBD connected)
python3 main.py
```

#### 4d. If Connection Fails

Check troubleshooting section below →

**👉 DO THIS FOURTH - Preparation for real hardware**

---

## STEP 5️⃣: TROUBLESHOOTING GUIDE (For Any Issues)

### 🔴 "ModuleNotFoundError: No module named 'PyQt6'"

**Fix:**
```bash
pip install PyQt6
# Or install all dependencies:
pip install -r requirements.txt
```

### 🔴 "No such file or directory: /dev/ttyUSB0"

**Why:** Wrong port or device not connected

**Fix:**
```bash
# List available ports again
ls /dev/tty*

# Update config/production.json with correct port
nano config/production.json
```

### 🔴 "Connection timeout" or "Serial port busy"

**Why:** Port already in use or device not responding

**Fix:**
```bash
# Try mock mode to verify software works
python3 main.py --mock

# Close any other terminal programs using the port
lsof /dev/ttyUSB0    # Linux - see what's using it

# Try a different baud rate in config
# (Usually 115200 works, try 9600 if it fails)
```

### 🔴 "P0171 code appears immediately"

**Why:** Genuine sensor issue or test mode active

**Check:**
```bash
# Are you in mock mode?
python3 main.py --mock    # Shows fake P0171 at end

# In production mode?
python3 main.py           # Should show real codes
```

### 🔴 GUI freezes or crashes

**Fix:**
```bash
# Check logs for errors
tail -f logs/pmmp.log

# Or with more verbose output
PMMP_LOGGING_LEVEL=DEBUG python3 main.py --mock

# If GUI crashing, try headless simulation instead
python3 simulate.py normal
```

### 🔴 Tests are failing

**Fix:**
```bash
# Run tests with verbose output
python3 -m unittest discover -s tests -v

# Run single test
python3 -m unittest tests.test_pmmp.TestConfiguration.test_config_loads -v

# Check if dependencies installed
pip install -r requirements.txt
```

### ✅ View System Logs

```bash
# Real-time log viewing
tail -f logs/pmmp.log

# Last 50 lines
tail -n 50 logs/pmmp.log

# Search for errors
grep ERROR logs/pmmp.log
```

---

## STEP 6️⃣: DEPLOYMENT (Production Setup)

### Quick Deployment Checklist:

- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Configure production.json with correct OBD port
- [ ] Test with: `python3 main.py`
- [ ] Create systemd service (optional, Linux only)
- [ ] Setup logging directory: `mkdir -p logs`
- [ ] Run in production mode

### Option A: Run Manually
```bash
cd ~/Desktop/Prog.-Devs./PMMP_Pro-G/pmmp_pro-g4
python3 main.py
```

### Option B: Create SystemD Service (Linux)

Create file `/etc/systemd/system/pmmp.service`:
```ini
[Unit]
Description=PMMP Pro-G4 Vehicle Diagnostics
After=network.target

[Service]
Type=simple
User=nato
WorkingDirectory=/home/nato/Desktop/Prog.-Devs./PMMP_Pro-G/pmmp_pro-g4
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable pmmp
sudo systemctl start pmmp
sudo systemctl status pmmp
```

### Option C: Docker Container (Advanced)

See [PRODUCTION_ROADMAP.md](PRODUCTION_ROADMAP.md#docker-deployment) for detailed Docker setup.

### Option D: PyInstaller Executable (End-User Distribution)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed main.py
# Creates standalone executable in dist/ folder
```

---

## 📊 YOUR ROADMAP

```
Step 1: RUN TESTS (30 sec)
        ✅ Verify all 16 tests pass
        ↓
Step 2: RUN SIMULATION (1 min)
        ✅ See complete pipeline in action
        ↓
Step 3: RUN GUI (2 min)
        ✅ Try mock mode, test commands
        ↓
Step 4: SETUP HARDWARE (30 min)
        ✅ Find OBD port, update config
        ✅ Test real connection
        ↓
Step 5: TROUBLESHOOTING (if needed)
        ✅ Fix any connection/import issues
        ↓
Step 6: DEPLOY (ongoing)
        ✅ Run in production
        ✅ Monitor logs
        ✅ Expand knowledge base
```

---

## 🚀 DO THIS RIGHT NOW

### The Fastest Path (5 minutes total):

```bash
cd ~/Desktop/Prog.-Devs./PMMP_Pro-G/pmmp_pro-g4

# 1. Run tests (30 seconds)
python3 main.py --test

# 2. Run simulation (60 seconds)
python3 simulate.py normal

# 3. Try GUI (60 seconds)
python3 main.py --mock
# Type: HELP, LIVE, DTC, EXIT
```

**After these 3 commands, you'll KNOW the system works.**

---

## 📁 Important Files

| File | Purpose |
|------|---------|
| [config/production.json](config/production.json) | Update OBD port here |
| [config/development.json](config/development.json) | Dev settings |
| [tests/test_pmmp.py](tests/test_pmmp.py) | All 16 unit tests |
| [simulate.py](simulate.py) | Headless runner |
| [main.py](main.py) | Entry point |
| [pmmp_controller.py](pmmp_controller.py) | Main orchestrator |
| [logs/pmmp.log](logs/pmmp.log) | System logs (generated) |

---

## 📞 Quick Reference

| Task | Command |
|------|---------|
| Test Everything | `python3 main.py --test` |
| Run Simulation | `python3 simulate.py normal` |
| GUI (Mock OBD) | `python3 main.py --mock` |
| Real Hardware | `python3 main.py` |
| View Logs | `tail -f logs/pmmp.log` |
| Debug Mode | `PMMP_LOGGING_LEVEL=DEBUG python3 main.py` |

---

## 🎯 After These Steps

Once you complete the roadmap above, you'll have:
- ✅ Verified all components work
- ✅ Seen the GUI and simulation
- ✅ Integrated with real hardware
- ✅ Resolved any issues
- ✅ Ready for production deployment

**Questions? Check [README.md](README.md) or [TESTING_GUIDE.md](TESTING_GUIDE.md)**
