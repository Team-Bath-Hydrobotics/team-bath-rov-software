import math
import pickle
import random
import socket
import struct
import time

from data_interface.network_type import NetworkEnum, NetworkHandler
from data_interface.rov_data import ROVData
from data_interface.vector_data import Vector3


class ROVTelemetrySimulator:
    """
    Simulates ROV telemetry data for testing purposes.

    Args:
        ports (dict): Dictionary of port configurations.
        running_flag (threading.Event): Flag to control the running state.
        frequency (int): Frequency in Hz to send telemetry data.
        controller_frequency (int): Frequency in Hz to check for controller input.
    """

    def __init__(
        self,
        ports,
        running_flag,
        socket_type: NetworkEnum,
        frequency=20,
        controller_frequency=10,
    ):
        self.ports = ports
        self.running = running_flag
        self.frequency = frequency
        self.controller_frequency = controller_frequency
        self.sim_time = 0.0
        self.socket = NetworkHandler(
            NetworkEnum.NONE, NetworkEnum(socket_type)
        ).get_output_network_socket()
        self.depth_trend = 0.0

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

    def start(self):
        """Send ROV telemetry data"""
        print("Starting telemetry data sender")

        self.socket.bind(("0.0.0.0", self.ports["data"]))
        self.socket.listen(1)

        try:
            while self.running:
                try:
                    print(
                        f"Telemetry waiting for connection on port {self.ports['data']}"
                    )
                    conn, addr = self.socket.accept()
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

                        time.sleep(1.0 / self.frequency)  # Use frequency for sleep time

                except socket.error as e:
                    if self.running:
                        print(f"Telemetry socket error: {e}")
                        time.sleep(1)

        except Exception as e:
            print(f"Telemetry error: {e}")
        finally:
            self.socket.close()
            print("Telemetry sender stopped")

    def receive_controller_input(self):
        """Receive and log controller input (handles length-prefixed data)"""
        print("Starting controller input receiver")

        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(("0.0.0.0", self.ports["control"]))
        self.socket.listen(1)

        try:
            while self.running:
                try:
                    print(
                        f"Controller input waiting for connection on port {self.ports['control']}"
                    )
                    conn, addr = self.socket.accept()
                    print(f"Controller input connected by {addr}")

                    while self.running:
                        try:
                            # Receive data
                            data = conn.recv(4096)
                            if not data:
                                break

                            # Try different approaches to find the pickle data
                            controller_data = None

                            # Approach 1: Try the data as-is
                            try:
                                controller_data = pickle.loads(data)
                            except pickle.UnpicklingError:
                                pass

                            # Skip first 20 bytes
                            if controller_data is None:
                                try:
                                    controller_data = pickle.loads(data[20:])
                                except (pickle.UnpicklingError, IndexError):
                                    pass
                            # If we successfully parsed the data, show it
                            if controller_data is not None:
                                print(
                                    f"Controller: Axes={len(controller_data.get('axes', []))} "
                                    f"Buttons={sum(controller_data.get('buttons', []))} "
                                    f"Hats={controller_data.get('hats', [])}"
                                )

                        except (BrokenPipeError, ConnectionResetError):
                            print("Controller input client disconnected")
                            break
                        except Exception as e:
                            print(f"Error processing controller data: {e}")

                except socket.error as e:
                    if self.running:
                        print(f"Controller input socket error: {e}")
                        time.sleep(
                            1.0 / self.controller_frequency
                        )  # Use controller frequency for sleep time

        except Exception as e:
            print(f"Controller input error: {e}")
        finally:
            self.socket.close()
            print("Controller input receiver stopped")
