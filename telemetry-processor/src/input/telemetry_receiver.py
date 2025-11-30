"""Telemetry receiver for UDP/TCP input from Jetson."""

import json
import socket
import threading
from typing import Callable, Optional

from data_interface.network_type import NetworkEnum, NetworkHandler
from data_interface.telemetry_data import TelemetryData


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
            self.socket.bind((self.host, self.port))
            print(f"Telemetry receiver listening on UDP {self.host}:{self.port}")
        elif self.network_type == NetworkEnum.TCP:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(1)
            print(f"Telemetry receiver listening on TCP {self.host}:{self.port}")

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
        while self.running:
            try:
                if self.network_type == NetworkEnum.UDP:
                    data, addr = self.socket.recvfrom(self.buffer_size)
                    self._process_data(data)
                elif self.network_type == NetworkEnum.TCP:
                    conn, addr = self.socket.accept()
                    print(f"TCP connection from {addr}")
                    self._handle_tcp_connection(conn)
            except socket.error as e:
                if self.running:
                    print(f"Socket error: {e}")
            except Exception as e:
                if self.running:
                    print(f"Receive error: {e}")

    def _handle_tcp_connection(self, conn: socket.socket):
        """Handle a TCP connection."""
        try:
            while self.running:
                data = conn.recv(self.buffer_size)
                if not data:
                    break
                self._process_data(data)
        finally:
            conn.close()

    def _process_data(self, data: bytes):
        """Process received data and invoke callback."""
        try:
            decoded = data.decode("utf-8")
            parsed = json.loads(decoded)
            telemetry = TelemetryData(
                timestamp=parsed.get("timestamp", 0.0),
                sensor_id=parsed.get("sensor_id", "unknown"),
                value=parsed.get("value", 0.0),
                unit=parsed.get("unit"),
                metadata=parsed.get("metadata"),
            )
            if self.callback:
                self.callback(telemetry)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"Failed to parse telemetry data: {e}")
