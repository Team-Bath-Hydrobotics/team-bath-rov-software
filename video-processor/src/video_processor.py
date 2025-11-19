import argparse
import signal
import sys
import threading
import time

from back_pressure_queue import BackpressureQueue
from data_interface.network_type import NetworkEnum
from metrics.metrics_monitor import MetricsMonitor
from mpegts.mpegts_client import MPEGTSClient
from mpegts.mpegts_server import MPEGTSServer


class VideoProcessor:
    """Video Processor to coordinate MPEGTS receiving and sending along with preprocessing"""

    def __init__(self, video_feeds, network_config):
        if video_feeds[0] is None or len(video_feeds[0]) == 0:
            print("No input video feeds configured, exiting.")
            sys.exit(1)

        self.input_video_feeds = video_feeds[0]
        self.output_video_feeds = video_feeds[1]

        (
            self.host_ip,
            self.target_ip,
            self.input_base_video_port,
            self.output_base_video_port,
            self.input_network_type,
            self.output_network_type,
        ) = parse_network_args(network_config)

        self.running = False

        # Frame processing
        self.servers = {}
        self.clients = {}
        self.threads = []
        self.frame_queues = {}

    def start(self):
        """Start video processor"""
        print("Starting Video Processor with MPEGTS...")

        # Wait for simulator to be fully ready
        print("Waiting for simulator to initialize...")
        time.sleep(3)
        self.running = True

        # Map feed id -> feed config for input and output feeds
        input_map = {
            self.extract_feed_id(cfg): cfg
            for cfg in self.input_video_feeds
            if cfg is not None
        }
        output_map = {
            self.extract_feed_id(cfg): cfg
            for cfg in self.output_video_feeds
            if cfg is not None
        }

        threads = []  # Initialize threads list
        idx = -1
        for feed_id, input_cfg in input_map.items():
            idx += 1
            if feed_id not in output_map:
                print(
                    f"Warning: No matching output feed for input feed ID {feed_id}, ignoring input {feed_id}"
                )
                continue

            output_cfg = output_map[feed_id]
            if input_cfg is None or output_cfg is None:
                print(
                    f"Error: Could not find settings for feed ID {feed_id}, skipping."
                )
                continue

            print(f"Setting up feed ID {feed_id}...")
            input_feed_settings = input_cfg.get("feed_settings", input_cfg)
            output_feed_settings = output_cfg.get("feed_settings", output_cfg)
            backpressure_queue_settings = input_cfg.get(
                "backpressure_queue_settings", {}
            )

            # Create frame queue for this feed
            max_queue_size, queue_timeout_ms = self.parse_backpressure_args(
                backpressure_queue_settings
            )
            print(
                f"Feed {feed_id}: Creating backpressure queue with max size {max_queue_size} and timeout {queue_timeout_ms} ms"
            )
            frame_queue = BackpressureQueue(
                max_queue_size=max_queue_size, queue_timeout_ms=queue_timeout_ms
            )
            self.frame_queues[feed_id] = frame_queue

            # Calculate ports for this feed
            input_port = self.input_base_video_port + idx
            output_port = self.output_base_video_port + idx

            # Create MPEGTS client (receives from simulator)
            client = MPEGTSClient(
                host_ip=self.host_ip,
                stream_id=feed_id,
                port=input_port,
                input_config=input_feed_settings,
                output_config=output_feed_settings,
                frame_queue=frame_queue,
                network_type=NetworkEnum(self.input_network_type),
            )
            self.clients[feed_id] = client

            # Create MPEGTS server (sends UDP output)
            server = MPEGTSServer(
                target_ip=self.target_ip,
                stream_id=feed_id,
                port=output_port,
                input_config=output_feed_settings,
                output_config={},
                frame_queue=frame_queue,
                network_type=NetworkEnum(self.output_network_type),
            )
            self.servers[feed_id] = server

            # Start client thread (receiver)
            client_thread = threading.Thread(
                target=self.start_client_delayed, args=(client, idx * 0.5)
            )
            client_thread.daemon = True
            threads.append(client_thread)

            # Start server thread (sender)
            server_thread = threading.Thread(target=server.start)
            server_thread.daemon = True
            threads.append(server_thread)

        # Start all threads
        for thread in threads:
            thread.start()

        print("Video Processor started!")
        signal.signal(signal.SIGINT, self.signal_handler)

        while self.running:
            time.sleep(5)
            # Print queue status
            for feed_id in self.frame_queues.keys():
                queue_size = self.frame_queues[feed_id].queue.qsize()
                dropped = self.frame_queues[feed_id].dropped_frames
                print(f"Feed {feed_id}: Queue size: {queue_size}, Dropped: {dropped}")

        # Cleanup servers and clients
        for server in self.servers.values():
            server.stop()
        for client in self.clients.values():
            client.stop()

    def start_client_delayed(self, client, delay):
        time.sleep(delay)
        client.start()

    def signal_handler(self, sig, frame):
        print("\nReceived interrupt signal...")
        self.running = False
        for server in self.servers.values():
            server.stop()
        for client in self.clients.values():
            client.stop()
        sys.exit(0)

    def extract_feed_id(self, feed_config):
        return feed_config.get("id", -1)

    def parse_backpressure_args(self, config):
        print(f"Parsing backpressure args for feed config: {config}")
        max_queue_size = config.get("max_queue_size", 10000)
        queue_timeout_ms = config.get("queue_timeout_ms", 500)

        print(
            f"Backpressure settings: max_queue_size={max_queue_size}, queue_timeout_ms={queue_timeout_ms}"
        )

        return max_queue_size, queue_timeout_ms


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


def parse_video_feeds(video_config):
    input_feeds = video_config.get("input_feeds", [])
    output_feeds = video_config.get("output_feeds", [])
    return (input_feeds, output_feeds)


def parse_network_args(network_config):
    input_base_video_port = network_config.get("input_base_video_port", 6000)
    host_ip = network_config.get("host_ip", "127.0.0.1")
    target_ip = network_config.get("target_ip", "127.0.0.1")
    output_video_base_port = network_config.get("output_base_video_port", 8554)
    input_network_type = network_config.get("input_network_type", "")
    output_network_type = network_config.get("output_network_type", "")
    return (
        host_ip,
        target_ip,
        input_base_video_port,
        output_video_base_port,
        input_network_type,
        output_network_type,
    )


def parse_filter_args(feed_config):
    filter_settings = feed_config.get("filter_settings", {"filters": []})
    return filter_settings


def main():
    parser = argparse.ArgumentParser(description="ROV Telemetry and Video Simulator")
    parser.add_argument(
        "--config", type=str, help="JSON file video processor configurations"
    )

    args = parser.parse_args()
    metrics_monitor = MetricsMonitor(memory_threshold=400.0)

    # Start monitoring
    metrics_monitor.start()
    video_config, network_config = parse_config_args(args)
    video_feeds = parse_video_feeds(video_config)

    video_processor = VideoProcessor(video_feeds, network_config)
    video_processor.start()


if __name__ == "__main__":
    main()
