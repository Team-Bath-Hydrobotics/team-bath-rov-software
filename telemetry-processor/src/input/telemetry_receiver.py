"""Telemetry receiver for UDP/TCP input from Jetson."""

import pickle
import socket
import struct
import threading
import time
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
        
        # Try to connect with retries
        max_retries = 5
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                self.socket = self._network_handler.get_input_network_socket()
                
                if self.network_type == NetworkEnum.UDP:
                    self.socket.connect((self.host, self.port))
                    print(f"Telemetry receiver connected via UDP to {self.host}:{self.port}")
                    break
                elif self.network_type == NetworkEnum.TCP:
                    self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    self.socket.connect((self.host, self.port))
                    print(f"Telemetry receiver connected via TCP to {self.host}:{self.port}")
                    break
            except ConnectionRefusedError:
                if attempt < max_retries - 1:
                    print(f"Connection refused. Retrying in {retry_delay} seconds... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                else:
                    print(f"Failed to connect after {max_retries} attempts. Starting in disconnected mode...")
                    # Continue anyway - will try to reconnect in receive loop
                    break
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"Connection error: {e}. Retrying in {retry_delay} seconds... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                else:
                    print(f"Failed to connect after {max_retries} attempts: {e}")
                    break

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
        reconnect_delay = 5  # seconds between reconnection attempts
        
        while self.running:
            # Check if we have a valid socket connection
            if not self.socket:
                try:
                    print(f"Attempting to connect to {self.host}:{self.port}...")
                    self.socket = self._network_handler.get_input_network_socket()
                    
                    if self.network_type == NetworkEnum.TCP:
                        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    
                    self.socket.connect((self.host, self.port))
                    print(f"Successfully connected to {self.host}:{self.port}")
                except Exception as e:
                    print(f"Connection failed: {e}. Retrying in {reconnect_delay} seconds...")
                    time.sleep(reconnect_delay)
                    continue
            
            try:
                if self.network_type == NetworkEnum.UDP:
                    data, addr = self.socket.recvfrom(self.buffer_size)
                    self._process_data(data)
                elif self.network_type == NetworkEnum.TCP:
                    data = self.socket.recv(self.buffer_size)
                    if not data:
                        print("Connection closed by server. Will attempt to reconnect...")
                        self.socket.close()
                        self.socket = None
                        time.sleep(reconnect_delay)
                        continue
                    self._process_data(data)
            except socket.error as e:
                if self.running:
                    print(f"Socket error: {e}. Will attempt to reconnect...")
                    if self.socket:
                        self.socket.close()
                        self.socket = None
                    time.sleep(reconnect_delay)
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
