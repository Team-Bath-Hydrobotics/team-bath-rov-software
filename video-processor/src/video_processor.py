import argparse
import json
import queue as pyqueue
import signal
import sys
import threading
import time

from back_pressure_queue import BackpressureQueue
from filters.basic_filters import Filter
from streaming.rtp_client import RTPClient
from streaming.websocket_sender import FrameWebSocketServer

from common.metrics.metrics_monitor import MetricsMonitor
from common.network.network_type import NetworkEnum


class VideoProcessor:
    """Coordinates RTSP ingestion + filtering + queueing + websocket relay"""

    def __init__(self, video_feeds, network_config, client_resilience_config):
        if not video_feeds or not video_feeds[0]:
            print("No input video feeds configured, exiting.")
            sys.exit(1)

        self.input_video_feeds = video_feeds[0]
        self.output_video_feeds = video_feeds[1]
        self.client_resilience_config = client_resilience_config

        (
            self.host_ip,
            self.target_ip,
            self.input_base_video_port,
            self.output_base_video_port,
            self.input_network_type,
            self.output_network_type,
            self.ws_relay_enabled,
            self.ws_relay_base_port,
        ) = parse_network_args(network_config)

        self.running = False
        self.clients = {}
        self.frame_queues = {}
        self.ws_servers = {}
        self.threads = []

    # -------------------------
    # WS forwarder (CRITICAL MISSING PIECE)
    # -------------------------
    def _ws_forwarder(self, feed_id, queue, ws_server):
        print(f"[WS-FWD] started feed={feed_id}")
        print(f"[WS] feed={feed_id} port={self.ws_relay_base_port + int(feed_id)}")

        while self.running:
            try:
                frame, metadata = queue.get()
                ws_server.broadcast(frame)
            except pyqueue.Empty:
                # normal: no frame available yet
                continue
            except Exception as e:
                import traceback

                print(f"[WS-FWD] error feed={feed_id}: {repr(e)}")
                traceback.print_exc()

    # -------------------------
    # startup
    # -------------------------
    def start(self):
        print("Starting Video Processor...")
        time.sleep(2)
        self.running = True

        input_map = {self.extract_feed_id(c): c for c in self.input_video_feeds if c}
        output_map = {self.extract_feed_id(c): c for c in self.output_video_feeds if c}

        idx = 0

        for feed_id, input_cfg in input_map.items():
            if feed_id not in output_map:
                continue

            output_cfg = output_map[feed_id]
            input_settings = input_cfg.get("feed_settings", input_cfg)

            queue_cfg = input_cfg.get("backpressure_queue_settings", {})
            max_q = queue_cfg.get("max_queue_size", 10000)
            timeout = queue_cfg.get("queue_timeout_ms", 500)

            frame_queue = BackpressureQueue(max_q, timeout)
            self.frame_queues[feed_id] = frame_queue

            # -------------------------
            # WebSocket server
            # -------------------------
            ws_server = FrameWebSocketServer(port=self.ws_relay_base_port + idx)
            ws_server.start()
            self.ws_servers[feed_id] = ws_server

            # -------------------------
            # WS forwarder thread (THIS WAS MISSING)
            # -------------------------
            fwd_thread = threading.Thread(
                target=self._ws_forwarder,
                args=(feed_id, frame_queue, ws_server),
                daemon=True,
            )
            self.threads.append(fwd_thread)

            # -------------------------
            # RTP client
            # -------------------------
            client = RTPClient(
                host_ip=self.host_ip,
                stream_id=feed_id,
                port=self.input_base_video_port,
                input_config=input_settings,
                output_config=output_cfg,
                frame_queue=frame_queue,
                network_type=NetworkEnum(self.input_network_type),
                resilience_config=self.client_resilience_config,
                filter=Filter(input_cfg.get("filter_settings", {}).get("filters", [])),
            )

            self.clients[feed_id] = client

            # delayed start
            t = threading.Thread(
                target=self._delayed_start,
                args=(client, idx * 1.5),
                daemon=True,
            )
            self.threads.append(t)

            idx += 1

        # start threads
        for t in self.threads:
            t.start()

        signal.signal(signal.SIGINT, self._shutdown)

        print("Video Processor running")

        while self.running:
            time.sleep(5)
            for fid, q in self.frame_queues.items():
                print(f"Feed {fid}: qsize={q.qsize()} dropped={q.dropped_frames}")

        print("Stopping...")
        for c in self.clients.values():
            c.stop()

    # -------------------------
    # helpers
    # -------------------------
    def _delayed_start(self, client, delay):
        time.sleep(delay)
        client.start()

    def _shutdown(self, sig, frame):
        self.running = False

    def extract_feed_id(self, cfg):
        return cfg.get("id", -1)


# -------------------------
# config helpers
# -------------------------
def parse_network_args(network_config):
    return (
        network_config.get("host_ip", "127.0.0.1"),
        network_config.get("target_ip", "127.0.0.1"),
        network_config.get("input_base_video_port", 6000),
        network_config.get("output_base_video_port", 8554),
        network_config.get("input_network_type", ""),
        network_config.get("output_network_type", ""),
        network_config.get("websocket_relay", {}).get("enabled", False),
        network_config.get("websocket_relay", {}).get("base_port", 50000),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str)
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = json.load(f)

    metrics = MetricsMonitor(memory_threshold=400.0)
    metrics.start()

    vp = VideoProcessor(
        (cfg["video_config"]["input_feeds"], cfg["video_config"]["output_feeds"]),
        cfg["network"],
        cfg["network"].get("client_resilience", {}),
    )

    vp.start()
    metrics.stop()


if __name__ == "__main__":
    main()
