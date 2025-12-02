import pickle
import random
import socket
import struct
import time

from data_interface.stdout_data import StdoutType

from common.common.network.network_type import NetworkEnum, NetworkHandler


class StdoutSimulator:
    """
    Simulates stdout/logging data for testing purposes.

    Args:
        ports (dict): Dictionary of port configurations.
        running_flag (threading.Event): Flag to control the running state.
        frequency (int): Frequency in Hz to send stdout data.
    """

    def __init__(self, ports, running_flag, socket_type: NetworkEnum, frequency=1):
        self.ports = ports
        self.running = running_flag
        self.frequency = frequency
        self.socket = NetworkHandler(
            NetworkEnum.NONE, NetworkEnum(socket_type)
        ).get_output_network_socket()

    def start(self):
        """Send simulated stdout/logging data"""
        print("Starting stdout data sender")

        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(("0.0.0.0", self.ports["stdout"]))
        self.socket.listen(1)

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
                    conn, addr = self.socket.accept()
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

                        time.sleep(1.0 / self.frequency)  # Use frequency for sleep time

                except socket.error as e:
                    if self.running:
                        print(f"Stdout socket error: {e}")
                        time.sleep(1.0 / self.frequency)  # Use frequency for sleep time

        except Exception as e:
            print(f"Stdout error: {e}")
        finally:
            self.socket.close()
            print("Stdout sender stopped")
