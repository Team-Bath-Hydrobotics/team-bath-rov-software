import math
import pickle
import random
import socket
import struct
import time

from data_interface.float_data import FloatData

from common.common.network.network_type import NetworkEnum, NetworkHandler


class FloatTelemetrySimulator:
    """
    Simulates float telemetry data for testing purposes.

    Args:
        ports (dict): Dictionary of port configurations.
        running_flag (threading.Event): Flag to control the running state.
        frequency (int): Frequency in Hz to send float data.
    """

    def __init__(self, ports, running_flag, socket_type: NetworkEnum, frequency=20):
        self.ports = ports
        self.running = running_flag
        self.frequency = frequency
        self.socket = NetworkHandler(
            NetworkEnum.NONE, NetworkEnum(socket_type)
        ).get_output_network_socket()
        self.sim_time = 0.0

    def generate_float_data(self):
        """Generate MATE float data"""
        float_data = FloatData()
        float_data.float_depth = (
            2.0 + 0.5 * math.sin(self.sim_time * 0.1) + random.uniform(-0.1, 0.1)
        )
        return float_data

    def start(self):
        """Send float telemetry data"""
        print("Starting float data sender")

        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(("0.0.0.0", self.ports["float_data"]))
        self.socket.listen(1)

        try:
            while self.running:
                try:
                    print(
                        f"Float data waiting for connection on port {self.ports['float_data']}"
                    )
                    conn, addr = self.socket.accept()
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

                        time.sleep(1.0 / self.frequency)  # Use frequency for sleep time

                except socket.error as e:
                    if self.running:
                        print(f"Float data socket error: {e}")
                        time.sleep(1)

        except Exception as e:
            print(f"Float data error: {e}")
        finally:
            self.socket.close()
            print("Float data sender stopped")
