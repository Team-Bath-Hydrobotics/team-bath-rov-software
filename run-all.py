import subprocess 
import sys
import shutil
import os
from pathlib import Path

## where the logs go
LOGS_DIR = Path(__file__).resolve().parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

ROOT = Path(__file__).resolve().parent

##detecting OS (for windows, linux and mac)
OS_WINDOWS = os.name == "nt"
OS_POSIX = os.name == "posix"
OS_NAME = ""
match os.name:
    case "nt":
        OS_NAME = "windows"
    case "posix":
        OS_NAME = "posix"
    case _:
        OS_NAME = "unknown"
print(f"Detected {OS_NAME} operating system")

## Commands to run
COMMANDS = {}
COMMANDS["video-processor"] = ["poetry", "run", "python", "src/video_processor.py", "--config", "processor_config.json"]
COMMANDS["telemetry-processor"] = ["ping", "127.0.0.1"]

processes = {}

## name is something like "telemetry"
## commnd is the actual command like [poetry run python src/telemetry_processor.py --config src/config.json]
for name, command in COMMANDS.items():
    
    log_dir = LOGS_DIR / f"{name}.log"
    log_dir.parent.mkdir(parents=True, exist_ok=True)

    print(ROOT, ROOT / name, (ROOT / name).is_dir())
    with open(log_dir, "w") as log:
        process = subprocess.Popen(command, stdout=None, stderr=None, cwd=ROOT/name, shell=True)
        processes[name] = process
        print(f"Process started with id: {process.pid}")
        print(f"Started {name} process, reporting logs to {log_dir}")
    

# This slop is supposed to shutdown all the processes but I hate it
try:
    while True:
        continue 
except KeyboardInterrupt:
    try:
        exit_codes = [p.wait(timeout=5) for p in processes.values()]
    except subprocess.TimeoutExpired:
        exit_codes = [p.terminate() for p in processes.value()]

"""
    subprocess
    signal
    os
    pathlib
    socket
    argparse
    shutil
    sys (sys.platform, platform)
    tomllib (or json)
"""


