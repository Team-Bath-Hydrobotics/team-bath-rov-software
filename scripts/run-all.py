import subprocess
import sys
import time
import os
import argparse
import threading
from pathlib import Path

# Path and where the logs go
ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# For printing and writing the processes output
print_lock = threading.Lock()
def pump(name, process, log_path):
    with open(log_path, "w", encoding="utf-8") as log:
    # Runs in it's own thread: copy one processes output to it's log file and the terminal
        for line in process.stdout:
            log.write(line)
            log.flush()
            with print_lock:
                print(f"[{name}] {line}", end="")
    # Loop ends naturally when process ends

# Commands to run
COMMANDS = {}
COMMANDS["video-processor"]     = ["poetry", "run", "python", "src/video_processor.py", "--config", "processor_config.json"]
COMMANDS["telemetry-processor"] = ["poetry", "run", "python", "src/telemetry_processor.py", "--config", "src/config.json"]
COMMANDS["packet-simulator"]    = ["poetry", "run", "python", "src/packet_simulator.py", "--config", "src/video_config.json"]

DOCKER_RUN_COMMAND = ["docker", "compose", "up", "-d", "--wait"]
DOCKER_SHUTDOWN_COMMAND = ["docker", "compose", "down"]

WEB_RUN_COMMAND = ["npm", "run", "dev"]

# None means that we will output to the terminal window, this is cluttered but useful for debugging
PROCESS_STDOUT = None

# Keeps track of the processes so we can shut them down
processes = {}

# Threads
threads = []

# This is passed to argparse as a type because it can resolve the directory instantly from runtime and give an appropriate error
def dir_arg(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"{path} is not a directory")
    return path

# Setup parser options
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
) # TODO, make some way that you can chose what processes output, while still running them all
parser.add_argument(
    "--web", "-w",
    default=ROOT.parent / "team-bath-rov-secondary-ui",
    type=dir_arg,
    help="Tells the script where the team-bath-secondary-ui folder is located. Passing this flag will start the website after the processes start successfully. Please note: Use the path relative to the current directory!"
)

parser.add_argument(
    "--local-video",
    action="store_true",
    help="Use the matching local video simulator and processor configs for generated camera feeds. By default, use the existing configs in each service directory.",
)
parser.add_argument(
    "--exclude", "-e",
    type=str,
    default=None,
    help="Tells the script which processes you wouldn't like to run. Only works when the \"run\" flag is to \"all\". This is because if you only want to run one thing, then you shouldn't need to exclude anything"
)
args = parser.parse_args()

if args.local_video:
    COMMANDS["video-processor"][-1] = str(ROOT / "config/local-video/processor.json")
    COMMANDS["packet-simulator"][-1] = str(ROOT / "config/local-video/simulator.json")

if args.run != "all":
    COMMANDS = {k: v for k, v in COMMANDS.items() if k in args.run}

if args.exclude != None:
    if args.exclude not in COMMANDS:
        print(f"{args.exclude} is not a recognised command! They are:")
        print(" 1. telemetry-processor")
        print(" 2. video-processor")
        print(" 3. packet-processor")
        sys.exit(1)
    else:
        COMMANDS.pop(args.exclude)


if "telemetry-processor" in COMMANDS:
    with open(LOGS_DIR  / "docker.log", "w") as docker_log:
        process = subprocess.Popen( DOCKER_RUN_COMMAND, cwd = ROOT / "mqtt", stdout = subprocess.PIPE, stderr = subprocess.STDOUT, text = True)
        for line in process.stdout:
            print(line, end = "")
            docker_log.write(line)
        process.wait()
    if process.returncode != 0:
        print("Docker failed to start! See", LOGS_DIR / "docker.log")
        sys.exit(1)

time.sleep(2) # TODO, replace with proper poll for the port. This just gives docker time to start, 
# increase if you are getting telemetry_processor errors on startup, something like "Failed to connect to MQTT broker"

env = {**os.environ, "PYTHONUNBUFFERED": "1"} # stop python children block buffering

# Main loop
for name, command in COMMANDS.items():
    log_path= LOGS_DIR / f"{name}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if args.verbose:
        # Different flags used as for this method we want to use the threads to handle their output
        process = subprocess.Popen(
            command,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=ROOT/name,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        t = threading.Thread(target=pump, args=(name, process, log_path), daemon=True)
        t.start()
        threads.append(t)

    else:
        with open(log_path, "w", encoding="utf-8") as log:
            process = subprocess.Popen(
                command,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                cwd=ROOT/name,
            )
    processes[name] = process
    print(f"Started {name}, logging to {log_path}")
    

web_cwd = None 
if args.web is not None:
    with open(LOGS_DIR / "web.log", "w") as web_log:
        web_cwd = args.web
        process = subprocess.Popen(WEB_RUN_COMMAND, stdout=web_log, stderr=subprocess.STDOUT, cwd=web_cwd)
        processes["web"] = process
        time.sleep(1)
        print("Web server should be open")
        print("Hosted at http://localhost:5173")


# Better shutdown method apparently, works the same
try:
    while True:
        for name, p in processes.items():
            if p.poll() is not None:
                print(f"{name} exited with code {p.returncode}")
        time.sleep(0.5)
except KeyboardInterrupt:
    print("CTRL-C")
    print("Shutting down...") 

    if "telemetry-processor" in COMMANDS:
        process = subprocess.run(DOCKER_SHUTDOWN_COMMAND, cwd=ROOT/"mqtt", capture_output=True, text=True)
        print("Docker composed down")

    try:
        # Tries to let them shutdown normally
        exit_codes = [p.wait(timeout=3) for p in processes.values()]
    except subprocess.TimeoutExpired:
        # Kills them if being polite takes too long
        exit_codes = [p.terminate() for p in processes.values()]

for t in threads:
    t.join(timeout=2)

print("All processess finished")
