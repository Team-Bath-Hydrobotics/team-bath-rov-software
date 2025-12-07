import argparse
import os
import threading
import time

from simulators.float_telemetry_simulator import FloatTelemetrySimulator
from simulators.rov_telemetry_simulator import ROVTelemetrySimulator
from simulators.std_out_simulator import StdoutSimulator
from simulators.video_simulator import VideoSimulator

from common.network.network_type import NetworkEnum


class PacketSimulator:
    def __init__(
        self,
        target_ip="127.0.0.1",
        video_generation_data=(None, None),
        base_video_port=52523,
        output_network_type="None",
    ):
        """Initialize the Packet Simulator"""
        self.target_ip = target_ip
        self.running = False
        self.video_files = (
            video_generation_data[0] if video_generation_data[0] is not None else []
        )
        self.video_feeds = (
            video_generation_data[1] if video_generation_data[1] is not None else []
        )
        self.base_video_port = base_video_port
        self.output_network_type = output_network_type

        if self.output_network_type != NetworkEnum.NONE:
            SystemError(f"Unsupported output network type: {self.output_network_type}")

        print(video_generation_data)
        # Create and set threading events for each simulator
        self.float_running = threading.Event()
        self.rov_running = threading.Event()
        self.video_running = threading.Event()
        self.stdout_running = threading.Event()

        # Set all events to True initially
        self.float_running.set()
        self.rov_running.set()
        self.video_running.set()
        self.stdout_running.set()

        self.float_ports = {
            "float_data": 52625,
        }

        self.rov_ports = {
            "data": 52525,
            "control": 52526,
        }

        self.stdout_ports = {
            "stdout": 52535,
        }

        self.ports = {**self.float_ports, **self.rov_ports, **self.stdout_ports}
        # Pass the shared threading events to simulators
        self.float_simulator = FloatTelemetrySimulator(
            self.float_ports, self.float_running, self.output_network_type, frequency=20
        )
        self.video_simulator = VideoSimulator(
            base_video_port,
            self.video_running,
            self.output_network_type,
            self.video_feeds,
            self.video_files,
        )
        self.rov_simulator = ROVTelemetrySimulator(
            self.rov_ports,
            self.output_network_type,
            frequency=20,
            controller_frequency=10,
        )
        self.stdout_simulator = StdoutSimulator(
            self.stdout_ports,
            self.stdout_running,
            self.output_network_type,
            frequency=1,
        )

    def start(self):
        """Start all simulation threads"""
        print("Starting telemetry and video simulator...")
        self.running = True

        threads = []

        # Start telemetry threads
        print("Starting float telemetry simulator...")
        threads.append(threading.Thread(target=self.float_simulator.start))

        print("Starting ROV telemetry simulator...")
        threads.append(threading.Thread(target=self.rov_simulator.start))

        print("Starting stdout simulator...")
        threads.append(threading.Thread(target=self.stdout_simulator.start))

        # Start all threads
        for thread in threads:
            thread.daemon = True
            thread.start()

        # Start video simulator directly (it manages its own threads)
        print("Starting video simulator...")
        self.video_simulator.start()

        print("All simulator threads started!")
        print(f"Telemetry data: port {self.ports['data']}")
        print(f"Float data: port {self.ports['float_data']}")
        print(f"Stdout data: port {self.ports['stdout']}")
        print(f"Controller input: port {self.ports['control']}")

        for i, feed in enumerate(self.video_feeds):
            port = self.video_simulator.base_video_port + i
            video_source = self.video_files.get(i, "generated pattern")
            print(
                f"Video feed {i}: port {port} "
                f"({feed['width']}x{feed['height']} @ {feed['fps']}fps, {feed['format']}) "
                f"- Source: {video_source}"
            )

        print("\nSimulator ready! Video feeds are waiting for connections...")
        print(
            "Start the video processor to connect to the feeds and the telemetry processor to connect to the telemetry ports."
        )

        try:
            while True:
                time.sleep(1)
                # Check if video threads are still alive
                if hasattr(self.video_simulator, "threads"):
                    alive_count = sum(
                        1 for t in self.video_simulator.threads if t.is_alive()
                    )
                    total_threads = len(self.video_simulator.threads)
                    if alive_count != total_threads:
                        print(
                            f"Warning: {total_threads - alive_count} video feed threads have stopped!"
                        )
                if hasattr(self.rov_simulator, "thread"):
                    if not self.rov_simulator.thread.is_alive():
                        print("Warning: ROV telemetry simulator thread has stopped!")
                if hasattr(self.float_simulator, "thread"):
                    if not self.float_simulator.thread.is_alive():
                        print("Warning: Float telemetry simulator thread has stopped!")
                if hasattr(self.stdout_simulator, "thread"):
                    if not self.stdout_simulator.thread.is_alive():
                        print("Warning: Stdout simulator thread has stopped!")

        except KeyboardInterrupt:
            print("\nShutting down simulator...")
            self.running = False

            # Clear all threading events to stop simulators
            self.float_running.clear()
            self.rov_running.clear()
            self.video_running.clear()
            self.stdout_running.clear()

            self.video_simulator.stop()

            time.sleep(2)
            print("Simulator stopped.")


def parse_config_args(arg):
    if arg.config:
        import json

        with open(arg.config, "r") as f:
            config = json.load(f)
        video_config = config.get("video_config", {})
        network_config = config.get("network", {})
    else:
        print("No configuration file provided, using default settings.")
        video_config = {}
        network_config = {}
    return video_config, network_config


def parse_video_args(video_config):
    feeds = video_config.get(
        "feeds", [{"width": 1920, "height": 1080, "fps": 30, "format": "stereo"}]
    )
    video_file_dir = video_config.get("input_file_dir", "")
    video_file_paths = {}
    print(f"Video file directory: {video_file_dir}")
    if not os.path.exists(video_file_dir):
        print(
            f"Warning: Video file directory not found running with auto generated data: {video_file_dir}"
        )
        return video_file_paths, feeds

    for i, file in enumerate(os.listdir(video_file_dir)):
        filepath = os.path.join(video_file_dir, file)
        video_file_paths[i] = filepath

    return (video_file_paths, feeds)


def parse_network_args(network_config):
    base_video_port = network_config.get("base_video_port", 52523)
    host_ip = network_config.get("host_ip", "127.0.0.1")
    output_network_type = network_config.get("output_network_type", "udp")
    return base_video_port, host_ip, output_network_type


def main():
    parser = argparse.ArgumentParser(description="ROV Telemetry and Video Simulator")
    parser.add_argument("--config", type=str, help="JSON file simulator configurations")

    args = parser.parse_args()
    video_config, network_config = parse_config_args(args)
    video_generation_data = parse_video_args(video_config)
    base_video_port, host_ip, output_network_type = parse_network_args(network_config)

    simulator = PacketSimulator(
        target_ip=host_ip,
        video_generation_data=video_generation_data,
        base_video_port=base_video_port,
        output_network_type=output_network_type,
    )
    simulator.start()


if __name__ == "__main__":
    main()
