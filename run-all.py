import subprocess 
import sys
import time
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

DOCKER_RUN_COMMAND = ["docker", "compose", "up", "-d", "--wait"]
DOCKER_SHUTDOWN_COMMAND = ["docker", "compose", "down"]
docker_started                  = False

WEB_RUN_COMMAND = ["npm", "run", "dev"]

## None means that we will output to the terminal window, this is cluttered but useful for debugging
PROCESS_STDOUT = None

## Keeps track of the processes so we can shut them down
processes = {}

## This is passed to argparse as a type because it can resolve the directory instantly from runtime and give an appropriate error
def dir_arg(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"{path} is not a directory")
    return path

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
) ## TODO, make some way that you can chose what processes output, while still running them all
parser.add_argument(
    "--web", "-w",
    type=dir_arg,
    help="Tells the script where the team-bath-secondary-ui folder is located. Passing this flag will start the website after the processes start successfully. Please note: Use the path relative to the current directory!"
)


## TODO
##parser.add_argument(
    ##"--append", "-a",
    ##action="store_true",
    ##help="Append to log files. This means that instead of replacing the log files every time it is run, it appends them, maybe with a timestamp?"
##)
args = parser.parse_args()

if args.run != "all":
    COMMANDS = {k: v for k, v in COMMANDS.items() if k in args.run}

if COMMANDS["telemetry-processor"] is not None:
    with open(LOGS_DIR  / "docker.log", "w") as docker_log:
        procces = subprocess.Popen( DOCKER_RUN_COMMAND, cwd = ROOT / "mqtt", stdout = subprocess.PIPE, stderr = subprocess.STDOUT, text = True)
        for line in procces.stdout:
            print(line, end = "")
            docker_log.write(line)
        procces.wait()
    if procces.returncode != 0:
        print("Docker failed to start! See", LOGS_DIR / "docker.log")
        sys.exit(1)

time.sleep(2) ## TODO, replace with proper poll for the port. This just gives docker time to start, 
## increase if you are getting telemetry_processor errors on startup, something like "Failed to connect to MQTT broker"


## Main loop
for name, command in COMMANDS.items():
    log_dir = LOGS_DIR / f"{name}.log"
    log_dir.parent.mkdir(parents=True, exist_ok=True)

    with open(log_dir, "w") as log:

        if not args.verbose:
           PROCESS_STDOUT = log 

        ## This means we need to open docker
        if COMMANDS["telemetry-processor"] is not None and not docker_started:
            docker_started = True
        
        ## Runs the current process and outputs to PROCESS_STDOUT, usually log (unless verbose enabled)
        process = subprocess.Popen(command, stdout=PROCESS_STDOUT, stderr=subprocess.STDOUT, cwd=ROOT/name)
        processes[name] = process
        print(f"Started {name} process, reporting logs to {log_dir}")
    

web_cwd = ""
if args.web is not None:
    with open(LOGS_DIR / "web.log", "w") as web_log:
        web_cwd = args.web
        process = subprocess.Popen(WEB_RUN_COMMAND, stdout=web_log, stderr=subprocess.STDOUT, cwd=web_cwd)
time.sleep(1)
print("Web server should be open")
print("Hosted at http://localhost:5173")


## This slop is supposed to shutdown all the processes but I hate it and it doesn't work
## Only after they press CTRL-C ofcourse
try:
    while True:
        continue 
except KeyboardInterrupt:
    print("CTRL-C")
    print("Shutting down...") 
    _ = subprocess.run(DOCKER_SHUTDOWN_COMMAND, cwd=ROOT/"mqtt", capture_output=True, text=True)
    print("Docker closed")
    try:
        ## Tries to let them shutdown normally
        exit_codes = [p.wait(timeout=3) for p in processes.values()]
    except subprocess.TimeoutExpired:
        ## Kills them if being polite takes too long
        exit_codes = [p.terminate() for p in processes.values()]
print("All processess finished")
