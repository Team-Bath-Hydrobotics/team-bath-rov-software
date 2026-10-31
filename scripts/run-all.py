import subprocess
import sys
import time
import os
import argparse
import threading
from pathlib import Path

# Repository root and log directory
ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Serialize terminal output from worker threads.
print_lock = threading.Lock()
def pump(name, process, log_path):
    with open(log_path, "w", encoding="utf-8") as log:
        # Copy process output to its log file and the terminal.
        for line in process.stdout:
            log.write(line)
            log.flush()
            with print_lock:
                print(f"[{name}] {line}", end="")
    # Stop reading when the process closes its output stream.

# Commands to run
COMMANDS = {}
COMMANDS["video-processor"]     = ["poetry", "run", "python", "src/video_processor.py", "--config", "processor_config.json"]
COMMANDS["telemetry-processor"] = ["poetry", "run", "python", "src/telemetry_processor.py", "--config", "src/config.json"]
COMMANDS["packet-simulator"]    = ["poetry", "run", "python", "src/packet_simulator.py", "--config", "src/video_config.json"]

DOCKER_RUN_COMMAND = ["docker", "compose", "up", "-d", "--wait"]
DOCKER_SHUTDOWN_COMMAND = ["docker", "compose", "down"]

WEB_RUN_COMMAND = ["npm", "run", "dev"]

# None routes subprocess output to the terminal.
PROCESS_STDOUT = None

# Track child processes for shutdown.
processes = {}

# Threads
threads = []

# Resolve and validate directory arguments during parsing.
def dir_arg(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"{path} is not a directory")
    return path

# Setup parser options
parser = argparse.ArgumentParser(description="Start the services required to develop and run the Team Bath ROV software.")
parser.add_argument(
    "--run", "-r",
    type=str,
    help="Select a service to start, such as telemetry-processor or video-processor. Defaults to all services.",
    default="all",
)
parser.add_argument(
    "--verbose", "-v",
    action="store_true",
    help="Display service output in the terminal and write it to log files.",
) # TODO: Allow terminal output to be enabled for selected services.
parser.add_argument(
    "--web", "-w",
    default=ROOT.parent / "team-bath-rov-secondary-ui",
    type=dir_arg,
    help="Path to the secondary UI repository. Relative paths are resolved from the current directory. Defaults to the sibling team-bath-rov-secondary-ui directory."
)

parser.add_argument(
    "--no-local-video",
    action="store_true",
    help="Use the original video configs in each service directory instead of the default local video configs for generated camera feeds.",
)
parser.add_argument(
    "--exclude", "-e",
    type=str,
    default=None,
    help="Exclude a service from the selected processes."
)
args = parser.parse_args()

if not args.no_local_video:
    COMMANDS["video-processor"][-1] = str(ROOT / "config/local-video/processor.json")
    COMMANDS["packet-simulator"][-1] = str(ROOT / "config/local-video/simulator.json")

if args.run != "all":
    COMMANDS = {k: v for k, v in COMMANDS.items() if k in args.run}

if args.exclude != None:
    if args.exclude not in COMMANDS:
        print(f"{args.exclude} is not a recognised service. Available services:")
        print(" 1. telemetry-processor")
        print(" 2. video-processor")
        print(" 3. packet-simulator")
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
        print("Docker failed to start. See", LOGS_DIR / "docker.log")
        sys.exit(1)

# TODO: Replace the startup delay with a broker readiness check.
time.sleep(2)

env = {**os.environ, "PYTHONUNBUFFERED": "1"} # Disable output buffering in Python child processes.

# Main loop
for name, command in COMMANDS.items():
    log_path= LOGS_DIR / f"{name}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if args.verbose:
        # Stream process output through a dedicated logging thread.
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
        print("Web server process started")
        print("Hosted at http://localhost:5173")


# Monitor child processes and handle keyboard interruption.
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
        print("Docker Compose shutdown command completed")

    try:
        # Allow child processes time to exit.
        exit_codes = [p.wait(timeout=3) for p in processes.values()]
    except subprocess.TimeoutExpired:
        # Terminate child processes that exceed the shutdown timeout.
        exit_codes = [p.terminate() for p in processes.values()]

for t in threads:
    t.join(timeout=2)

print("All processes finished")
