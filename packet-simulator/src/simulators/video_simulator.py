import os
import socket
import subprocess
import threading
import time

from common.common.network.network_type import NetworkEnum, NetworkHandler


class VideoSimulator:
    def __init__(
        self,
        base_video_port,
        running_flag,
        socket_type: NetworkEnum,
        video_feeds=None,
        video_files=None,
    ):
        self.base_video_port = base_video_port
        self.running = running_flag
        self.socket_type = socket_type
        self.video_feeds = video_feeds if video_feeds is not None else []
        self.video_files = video_files if video_files is not None else {}
        self.ports = {}
        for i in range(len(self.video_feeds)):
            self.ports[f"feed_{i}"] = self.base_video_port + i

        print(f"VideoSimulator initialized with feeds: {self.video_feeds}")

    def get_ffmpeg_input_for_feed(self, feed_id, config):
        """Get FFmpeg input configuration for a specific feed"""
        # Check if we have a video file for this feed
        video_file = self.video_files.get(feed_id)

        if video_file and os.path.exists(video_file):
            print(f"Using video file for feed {feed_id}: {video_file}")

            if config["format"] == "stereo":
                # For stereo, we'll use the video file but create side-by-side layout
                return [
                    "-stream_loop",
                    "-1",  # Loop the video indefinitely
                    "-i",
                    video_file,
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=1000:duration=0",
                    "-filter_complex",
                    f"[0:v]scale={config['width'] // 2}:{config['height']},split[left][right];[left][right]hstack[v]",
                    "-map",
                    "[v]",
                    "-map",
                    "1:a",
                ]
            else:
                # For mono, just scale the video to match config
                return [
                    "-stream_loop",
                    "-1",  # Loop the video indefinitely
                    "-i",
                    video_file,
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=1000:duration=0",
                    "-filter_complex",
                    f"[0:v]scale={config['width']}:{config['height']}[v]",
                    "-map",
                    "[v]",
                    "-map",
                    "1:a",
                ]
        else:
            # Fallback to generated patterns
            if video_file:
                print(
                    f"Video file not found for feed {feed_id}: {video_file}, using generated pattern"
                )
            else:
                print(
                    f"No video file specified for feed {feed_id}, using generated pattern"
                )

            if config["format"] == "stereo":
                # For stereo feed, create different patterns for left/right
                return [
                    "-f",
                    "lavfi",
                    "-i",
                    (
                        f'mandelbrot=size={config["width"] // 2}x{config["height"]}'
                        f':rate={config["fps"]}'
                    ),
                    "-f",
                    "lavfi",
                    "-i",
                    (
                        f'life=size={config["width"] // 2}x{config["height"]}'
                        f':rate={config["fps"]}:mold=10'
                    ),
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=1000:duration=0",
                    "-filter_complex",
                    "[0:v][1:v]hstack=inputs=2[v]",
                    "-map",
                    "[v]",
                    "-map",
                    "2:a",
                ]
            else:
                # For mono feed, use varied test patterns based on feed_id
                patterns = [
                    "testsrc",
                    "testsrc2",
                    "rgbtestsrc",
                    "smptebars",
                    "mandelbrot",
                    "life",
                ]
                pattern = patterns[feed_id % len(patterns)]

                return [
                    "-f",
                    "lavfi",
                    "-i",
                    (
                        f'{pattern}=size={config["width"]}x{config["height"]}'
                        f':rate={config["fps"]}'
                    ),
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=1000:duration=0",
                    "-map",
                    "0:v",
                    "-map",
                    "1:a",
                ]

    def start_feed(self, port, config, feed_id):
        server_socket = NetworkHandler(
            NetworkEnum.NONE, NetworkEnum(self.socket_type)
        ).get_output_network_socket()
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("0.0.0.0", port))
        server_socket.listen(1)
        print(f"Video feed {feed_id} successfully bound to port {port}")

        while self.running.is_set():
            try:
                import select

                ready, _, _ = select.select([server_socket], [], [], 1.0)
                if not ready:
                    continue

                conn, addr = server_socket.accept()
                print(f"Video feed {feed_id} connected by {addr}")

                # Spawn a separate thread for streaming to this client
                threading.Thread(
                    target=self.forward_feed_to_client,
                    args=(conn, feed_id, config),
                    daemon=True,
                ).start()

            except Exception as e:
                print(f"Video feed {feed_id} socket error: {e}")
                time.sleep(1)

    def forward_feed_to_client(self, conn, feed_id, config):
        ffmpeg_cmd = (
            ["ffmpeg", "-loglevel", "error"]
            + self.get_ffmpeg_input_for_feed(feed_id, config)
            + [
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-tune",
                "zerolatency",
                "-crf",
                "23",
                "-g",
                str(config["fps"]),
                "-r",
                str(config["fps"]),
                "-c:a",
                "aac",
                "-f",
                "mpegts",
                "-",
            ]
        )

        ffmpeg_process = subprocess.Popen(
            ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0
        )

        try:
            while self.running.is_set() and ffmpeg_process.poll() is None:
                chunk = ffmpeg_process.stdout.read(4096)
                if not chunk:
                    break
                try:
                    conn.sendall(chunk)
                except (BrokenPipeError, ConnectionResetError, socket.error):
                    break
        finally:
            ffmpeg_process.terminate()
            try:
                ffmpeg_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                ffmpeg_process.kill()
            conn.close()
            print(f"Feed {feed_id}: Client connection closed")

    def start(self):
        """Start all video feeds"""
        print("Starting video simulator with all feeds")

        self.threads = []

        for i, feed in enumerate(self.video_feeds):
            port = self.ports[f"feed_{i}"]
            thread = threading.Thread(target=self.start_feed, args=(port, feed, i))
            thread.daemon = True
            self.threads.append(thread)
            thread.start()
            print(f"Started video feed {i} on port {port}")

        # Give threads a moment to start up properly
        time.sleep(2)
        print(f"Video simulator started with {len(self.threads)} feeds")

    def stop(self):
        """Stop the video simulator"""
        print("Stopping video simulator...")
        self.running.clear()
