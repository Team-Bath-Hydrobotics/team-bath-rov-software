import subprocess 
import sys
import shutil
import os
import argparse
from pathlib import Path

## Path and where the logs go
ROOT = Path(__file__).resolve().parent
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

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
COMMANDS["video-processor"]     = ["poetry", "run", "python", "src/video_processor.py", "--config", "processor_config.json"]
COMMANDS["telemetry-processor"] = ["poetry", "run", "python", "src/telemetry_processor.py", "--config", "src/config.json"]
COMMANDS["packet-simulator"]    = ["poetry", "run", "python", "src/packet_simulator.py", "--config", "src/video_config.json"]

DOCKER_RUN_COMMAND = ["docker", "compose", "up", "-d"]
DOCKER_SHUTDOWN_COMMAND = ["docker", "compose", "down"]
docker_started                  = False

## None means that we will output to the terminal window, this is cluttered but useful for debugging
PROCESS_STDOUT = None

## Keeps track of the processes so we can shut them down
processes = {}

## Setup parser options
parser = argparse.ArgumentParser(description="A run all script designed to spin up all the processes required to develop and run team-bath-software")
parser.add_argument(
    "--run", "-r",
    type=str,
    help="What to run with the script, default is all. Can specify specific process like telemetry-processor or video-processor",
    default="all",
)
parser.add_argument(
    "--verbose", "-v",
    action="store_true",
    help="Verbose output, shows all the output from the processes, still writes to log files aswell. Warning: Very cluttered if running all",
)
## TODO
##parser.add_argument(
    ##"--append", "-a",
    ##action="store_true",
    ##help="Append to log files. This means that instead of replacing the log files every time it is run, it appends them to "
##)
args = parser.parse_args()

if args.run != "all":
    COMMANDS = {k: v for k, v in COMMANDS.items() if k in args.run}
for name, command in COMMANDS.items():
    log_dir = LOGS_DIR / f"{name}.log"
    log_dir.parent.mkdir(parents=True, exist_ok=True)

    with open(log_dir, "w") as log:

        if not args.verbose:
           PROCESS_STDOUT = log 

        ## This means we need to open docker
        if COMMANDS["telemetry-processor"] is not None and not docker_started:
            docker_started = True
            result = subprocess.run(DOCKER_RUN_COMMAND, cwd=ROOT / "mqtt", capture_output=True, text=True)
            if "failed" in result.stderr:
                open(LOGS_DIR / "docker.log", "w") 
                log.write(result.stdout)
                print("Docker failed to start! Please check:", LOGS_DIR / "docker.log")
                print("You might need to Docker desktop!")
                exit();
            else:
                print("Docker started successfully!")
        
        ## Runs the current process and outputs to PROCESS_STDOUT, usually log (unless verbose enabled)
        process = subprocess.Popen(command, stdout=PROCESS_STDOUT, stderr=subprocess.STDOUT, cwd=ROOT/name, shell=True)
        processes[name] = process
        print(f"Started {name} process, reporting logs to {log_dir}")
    

# This slop is supposed to shutdown all the processes but I hate it and it doesn't work
try:
    while True:
        continue 
except KeyboardInterrupt:
    print("Shutting down...") 
    _ = subprocess.run(DOCKER_SHUTDOWN_COMMAND, cwd=ROOT/"mqtt", capture_output=True, text=True)
    print("Docker closed")
    try:
        exit_codes = [p.wait(timeout=3) for p in processes.values()]
    except subprocess.TimeoutExpired:
        exit_codes = [p.terminate() for p in processes.values()]

