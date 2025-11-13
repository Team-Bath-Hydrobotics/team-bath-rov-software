import math
import pickle
import random
import socket
import struct
import subprocess
import threading
import time
from dataclasses import dataclass, field


# Import your existing data structures (adjust paths as needed)
@dataclass
class Vector3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class ROVData:
    attitude: Vector3 = field(default_factory=Vector3)
    angular_acceleration: Vector3 = field(default_factory=Vector3)
    angular_velocity: Vector3 = field(default_factory=Vector3)
    acceleration: Vector3 = field(default_factory=Vector3)
    velocity: Vector3 = field(default_factory=Vector3)
    depth: float = 0.0
    ambient_temperature: float = 25.0
    ambient_pressure: float = 101.3
    internal_temperature: float = 30.0
    cardinal_direction: float = 0.0
    grove_water_sensor: int = 0
    actuator_1: float = 0.0
    actuator_2: float = 0.0
    actuator_3: float = 0.0
    actuator_4: float = 0.0
    actuator_5: float = 0.0
    actuator_6: float = 0.0


@dataclass
class FloatData:
    float_depth: float = 0.0


class StdoutType:
    ROV = "ROV"
    ROV_ERROR = "ROV_ERROR"
    UI = "UI"
    UI_ERROR = "UI_ERROR"


class TelemetryVideoSimulator:
    def __init__(self, target_ip="127.0.0.1"):
        self.target_ip = target_ip
        self.running = False

        # Port configuration (adjust to match your UI receiver)
        self.ports = {
            "data": 52525,
            "float_data": 52625,
            "stdout": 52535,
            "feed_0": 52524,
            "feed_1": 52523,
            "control": 52526,  # For receiving controller input
        }

        # Video settings for stress testing
        self.video_configs = [
            {
                "width": 1280,
                "height": 720,
                "fps": 60,
                "format": "stereo",
            },  # High bandwidth
            {"width": 640, "height": 480, "fps": 30, "format": "mono"},
        ]

        # Simulation state
        self.sim_time = 0.0
        self.depth_trend = 0.0

    def send_video_stream(self, port, config, feed_id):
        """Send MPEGTS video stream using FFmpeg that VideoRecv can decode"""
        print(f"Starting video stream {feed_id} on port {port}")

        # Create a TCP server socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("0.0.0.0", port))
        server_socket.listen(1)

        try:
            while self.running:
                try:
                    print(f"Video feed {feed_id} waiting for connection on port {port}")
                    conn, addr = server_socket.accept()
                    print(f"Video feed {feed_id} connected by {addr}")

                    # Enhanced test pattern with visible frame changes
                    if config["format"] == "stereo":
                        # For stereo feed, create different patterns for left/right
                        ffmpeg_cmd = [
                            "ffmpeg",
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
                            "-c:a",
                            "aac",
                            "-f",
                            "mpegts",
                            "-",
                        ]
                    else:
                        # For mono feed, use static test pattern

                        ffmpeg_cmd = [
                            "ffmpeg",
                            "-f",
                            "lavfi",
                            "-i",
                            "-i",
                            (
                                f'testsrc=size={config["width"]}x{config["height"]}'
                                f':rate={config["fps"]}'
                            ),
                            "-f",
                            "lavfi",
                            "-i",
                            "sine=frequency=1000:duration=0",
                            "-c:v",
                            "libx264",
                            "-preset",
                            "ultrafast",
                            "-tune",
                            "zerolatency",
                            "-c:a",
                            "aac",
                            "-f",
                            "mpegts",
                            "-",
                        ]

                    # Start FFmpeg process
                    ffmpeg_process = subprocess.Popen(
                        ffmpeg_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        bufsize=0,
                    )

                    try:
                        # Forward FFmpeg output to client
                        while self.running and ffmpeg_process.poll() is None:
                            chunk = ffmpeg_process.stdout.read(4096)
                            if not chunk:
                                break
                            try:
                                conn.sendall(chunk)
                            except (BrokenPipeError, ConnectionResetError):
                                print(f"Video feed {feed_id} client disconnected")
                                break

                    finally:
                        # Clean up FFmpeg process
                        if ffmpeg_process.poll() is None:
                            ffmpeg_process.terminate()
                            ffmpeg_process.wait(timeout=5)

                except socket.error as e:
                    if self.running:
                        print(f"Video feed {feed_id} socket error: {e}")
                        time.sleep(1)

        except Exception as e:
            print(f"Video feed {feed_id} error: {e}")
        finally:
            server_socket.close()
            print(f"Video feed {feed_id} stopped")

    def generate_telemetry_data(self):
        """Generate realistic ROV telemetry data"""
        # Simulate underwater movement with some realistic physics
        self.sim_time += 0.1

        # Depth with realistic underwater behavior
        self.depth_trend += random.uniform(-0.05, 0.05)
        self.depth_trend = max(-0.5, min(0.5, self.depth_trend))
        depth = 2.0 + self.depth_trend + 0.2 * math.sin(self.sim_time * 0.1)
        depth = max(0, depth)

        # Attitude with some drift and oscillation
        pitch = 2 * math.sin(self.sim_time * 0.2) + random.uniform(-1, 1)
        yaw = self.sim_time * 10 % 360
        roll = 1.5 * math.cos(self.sim_time * 0.15) + random.uniform(-0.5, 0.5)

        # Temperature variations
        ambient_temp = (
            25 + 2 * math.sin(self.sim_time * 0.05) + random.uniform(-0.5, 0.5)
        )
        internal_temp = 35 + 5 * math.sin(self.sim_time * 0.03) + random.uniform(-1, 1)

        # Pressure based on depth
        ambient_pressure = 101.3 + depth * 10.1 + random.uniform(-0.1, 0.1)

        rov_data = ROVData()
        rov_data.attitude = Vector3(pitch, yaw, roll)
        rov_data.angular_acceleration = Vector3(
            random.uniform(-0.1, 0.1),
            random.uniform(-0.1, 0.1),
            random.uniform(-0.1, 0.1),
        )
        rov_data.angular_velocity = Vector3(
            random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1)
        )
        rov_data.acceleration = Vector3(
            random.uniform(-0.5, 0.5),
            random.uniform(-0.5, 0.5),
            random.uniform(-0.5, 0.5),
        )
        rov_data.velocity = Vector3(
            random.uniform(-2, 2), random.uniform(-2, 2), random.uniform(-1, 1)
        )
        rov_data.depth = depth
        rov_data.ambient_temperature = ambient_temp
        rov_data.ambient_pressure = ambient_pressure
        rov_data.internal_temperature = internal_temp
        rov_data.cardinal_direction = yaw
        rov_data.grove_water_sensor = random.randint(0, 1)

        # Simulate thruster values
        for i in range(1, 7):
            setattr(rov_data, f"actuator_{i}", random.uniform(-100, 100))

        return rov_data

    def generate_float_data(self):
        """Generate MATE float data"""
        float_data = FloatData()
        float_data.float_depth = (
            2.0 + 0.5 * math.sin(self.sim_time * 0.1) + random.uniform(-0.1, 0.1)
        )
        return float_data

    def send_telemetry_data(self):
        """Send ROV telemetry data"""
        print("Starting telemetry data sender")

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("0.0.0.0", self.ports["data"]))
        server_socket.listen(1)

        try:
            while self.running:
                try:
                    print(
                        f"Telemetry waiting for connection on port {self.ports['data']}"
                    )
                    conn, addr = server_socket.accept()
                    print(f"Telemetry connected by {addr}")

                    while self.running:
                        rov_data = self.generate_telemetry_data()

                        try:
                            serialized_data = pickle.dumps(rov_data)
                            message = (
                                struct.pack("Q", len(serialized_data)) + serialized_data
                            )
                            conn.sendall(message)
                        except (BrokenPipeError, ConnectionResetError):
                            print("Telemetry client disconnected")
                            break

                        time.sleep(0.1)  # 10Hz telemetry rate

                except socket.error as e:
                    if self.running:
                        print(f"Telemetry socket error: {e}")
                        time.sleep(1)

        except Exception as e:
            print(f"Telemetry error: {e}")
        finally:
            server_socket.close()
            print("Telemetry sender stopped")

    def send_float_data(self):
        """Send float telemetry data"""
        print("Starting float data sender")

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("0.0.0.0", self.ports["float_data"]))
        server_socket.listen(1)

        try:
            while self.running:
                try:
                    print(
                        f"Float data waiting for connection on port {self.ports['float_data']}"
                    )
                    conn, addr = server_socket.accept()
                    print(f"Float data connected by {addr}")

                    while self.running:
                        float_data = self.generate_float_data()

                        try:
                            serialized_data = pickle.dumps(float_data)
                            message = (
                                struct.pack("Q", len(serialized_data)) + serialized_data
                            )
                            conn.sendall(message)
                        except (BrokenPipeError, ConnectionResetError):
                            print("Float data client disconnected")
                            break

                        time.sleep(0.5)  # 2Hz float data rate

                except socket.error as e:
                    if self.running:
                        print(f"Float data socket error: {e}")
                        time.sleep(1)

        except Exception as e:
            print(f"Float data error: {e}")
        finally:
            server_socket.close()
            print("Float data sender stopped")

    def send_stdout_data(self):
        """Send simulated stdout/logging data"""
        print("Starting stdout data sender")

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("0.0.0.0", self.ports["stdout"]))
        server_socket.listen(1)

        log_messages = [
            "System initialization complete",
            "Thruster calibration successful",
            "Depth sensor reading nominal",
            "Camera feed stable",
            "Temperature within normal range",
            "IMU calibration complete",
            "Pressure sensor operational",
            "Warning: High internal temperature detected",
            "Error: Thruster 3 overcurrent",
            "Info: Switching to backup camera",
        ]

        try:
            while self.running:
                try:
                    print(
                        f"Stdout waiting for connection on port {self.ports['stdout']}"
                    )
                    conn, addr = server_socket.accept()
                    print(f"Stdout connected by {addr}")

                    while self.running:
                        # Send batch of log messages
                        messages = []
                        for _ in range(random.randint(1, 3)):
                            msg_type = random.choice(
                                [StdoutType.ROV, StdoutType.ROV_ERROR]
                            )
                            msg_text = random.choice(log_messages)
                            messages.append(
                                (msg_type, f"[{time.time():.2f}] {msg_text}")
                            )

                        try:
                            serialized_data = pickle.dumps(messages)
                            message = (
                                struct.pack("Q", len(serialized_data)) + serialized_data
                            )
                            conn.sendall(message)
                        except (BrokenPipeError, ConnectionResetError):
                            print("Stdout client disconnected")
                            break

                        time.sleep(1.0)  # 1Hz log rate

                except socket.error as e:
                    if self.running:
                        print(f"Stdout socket error: {e}")
                        time.sleep(1)

        except Exception as e:
            print(f"Stdout error: {e}")
        finally:
            server_socket.close()
            print("Stdout sender stopped")

    def receive_controller_input(self):
        """Receive and log controller input (optional)"""
        print("Starting controller input receiver")

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("0.0.0.0", self.ports["control"]))
        server_socket.listen(1)

        try:
            while self.running:
                try:
                    print(
                        f"Controller input waiting for connection on port {self.ports['control']}"
                    )
                    conn, addr = server_socket.accept()
                    print(f"Controller input connected by {addr}")

                    while self.running:
                        try:
                            # Receive controller data
                            data = b""
                            payload_size = struct.calcsize("Q")

                            while len(data) < payload_size:
                                packet = conn.recv(4096)
                                if not packet:
                                    raise ConnectionResetError()
                                data += packet

                            packed_msg_size = data[:payload_size]
                            data = data[payload_size:]
                            msg_size = struct.unpack("Q", packed_msg_size)[0]

                            while len(data) < msg_size:
                                data += conn.recv(4096)

                            controller_data = pickle.loads(data[:msg_size])

                            if controller_data is not None:
                                print(
                                    f"Controller: Axes={len(controller_data.get('axes', []))} "
                                    f"Buttons={sum(controller_data.get('buttons', []))} "
                                    f"Hats={controller_data.get('hats', [])}"
                                )

                        except (BrokenPipeError, ConnectionResetError):
                            print("Controller input client disconnected")
                            break

                except socket.error as e:
                    if self.running:
                        print(f"Controller input socket error: {e}")
                        time.sleep(1)

        except Exception as e:
            print(f"Controller input error: {e}")
        finally:
            server_socket.close()
            print("Controller input receiver stopped")

    def start(self):
        """Start all simulation threads"""
        print("Starting telemetry and video simulator...")
        self.running = True

        threads = []

        # Start telemetry threads
        threads.append(threading.Thread(target=self.send_telemetry_data))
        threads.append(threading.Thread(target=self.send_float_data))
        threads.append(threading.Thread(target=self.send_stdout_data))
        threads.append(threading.Thread(target=self.receive_controller_input))

        # Start video threads
        for i, config in enumerate(self.video_configs):
            port = self.ports[f"feed_{i}"]
            thread = threading.Thread(
                target=self.send_video_stream, args=(port, config, i)
            )
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.daemon = True
            thread.start()

        print("All simulator threads started!")
        print(f"Telemetry data: port {self.ports['data']}")
        print(f"Float data: port {self.ports['float_data']}")
        print(f"Stdout data: port {self.ports['stdout']}")
        print(f"Controller input: port {self.ports['control']}")
        for i, config in enumerate(self.video_configs):
            print(
                f"Video feed {i}: port {self.ports[f'feed_{i}']} "
                f"({config['width']}x{config['height']} @ {config['fps']}fps, {config['format']})"
            )

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down simulator...")
            self.running = False
            time.sleep(2)


if __name__ == "__main__":
    simulator = TelemetryVideoSimulator()
    simulator.start()
