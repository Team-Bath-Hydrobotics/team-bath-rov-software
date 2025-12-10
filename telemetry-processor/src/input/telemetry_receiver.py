"""Telemetry receiver for UDP/TCP input from Jetson."""

import pickle
import socket
import struct
import threading
from typing import Callable, Optional

from common.data_interface import TelemetryData
from common.network.network_type import NetworkEnum, NetworkHandler


class TelemetryReceiver:
    """Receives telemetry data from Jetson over UDP or TCP."""

    def __init__(
        self,
        host: str,
        port: int,
        network_type: NetworkEnum,
        callback: Optional[Callable[[TelemetryData], None]] = None,
        buffer_size: int = 4096,
    ):
        self.host = host
        self.port = port
        self.network_type = network_type
        self.callback = callback
        self.buffer_size = buffer_size

        self.running = False
        self.socket: Optional[socket.socket] = None
        self.receive_thread: Optional[threading.Thread] = None

        self._network_handler = NetworkHandler(network_type, NetworkEnum.NONE)

    def start(self):
        """Start receiving telemetry data."""
        self.running = True
        self.socket = self._network_handler.get_input_network_socket()

        if self.network_type == NetworkEnum.UDP:
            self.socket.connect((self.host, self.port))
            print(f"Telemetry receiver listening on UDP {self.host}:{self.port}")
        elif self.network_type == NetworkEnum.TCP:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.connect((self.host, self.port))
            print(f"Telemetry receiver listening on TCP {self.host}:{self.port}")

        print("Starting telemetry receive loop...")
        self.receive_thread = threading.Thread(target=self._receive_loop)
        self.receive_thread.daemon = True
        self.receive_thread.start()

    def stop(self):
        """Stop receiving telemetry data."""
        self.running = False
        if self.socket:
            self.socket.close()
            self.socket = None

    def _receive_loop(self):
        """Main receive loop."""
        print("Starting telemetry receive loop")
        while self.running:
            try:
                if self.network_type == NetworkEnum.UDP:
                    data, addr = self.socket.recvfrom(self.buffer_size)
                    self._process_data(data)
                elif self.network_type == NetworkEnum.TCP:
                    data = self.socket.recv(self.buffer_size)
                    if not data:
                        print("Connection closed by server")
                        break
                    self._process_data(data)
            except socket.error as e:
                if self.running:
                    print(f"Socket error (connection failed): {e}")
                    break
            except Exception as e:
                if self.running:
                    print(f"Receive error (skipping packet): {e}")
                    continue

    def _process_data(self, data: bytes):
        """Process received data and invoke callback."""
        # unpickle each attribute and pass back as a list
        if len(data) < 8:
            print("Received incomplete data")
            return
        data_length = struct.unpack("Q", data[:8])[0]
        pickled_data = data[8 : 8 + data_length]

        # Unpickle the ROVData object
        rov_data = pickle.loads(pickled_data)
        if self.callback:
            self.callback(rov_data)
