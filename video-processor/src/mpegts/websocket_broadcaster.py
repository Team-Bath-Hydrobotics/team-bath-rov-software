import asyncio
import threading
import websockets

class WebSocketBroadcaster(threading.Thread):
    """Threaded WebSocket server for broadcasting MPEGTS frames"""

    def __init__(self, stream_id, base_port):
        super().__init__(daemon=True)
        self.stream_id = stream_id
        self.port = base_port + int(stream_id)
        self.clients = set()
        self._loop = None
        self._loop_ready = threading.Event()
        self.running = True

    async def _handler(self, websocket):
        client_addr = websocket.remote_address if hasattr(websocket, 'remote_address') else 'unknown'
        self.clients.add(websocket)
        print(f"WebSocket client connected to stream {self.stream_id} from {client_addr} (total clients: {len(self.clients)})")
        try:
            # Wait for close with a timeout to prevent indefinite hangs
            try:
                await asyncio.wait_for(websocket.wait_closed(), timeout=None)
            except asyncio.TimeoutError:
                print(f"WebSocket connection timeout for stream {self.stream_id} from {client_addr}")
        finally:
            self.clients.discard(websocket)  # Use discard to avoid KeyError if already removed by _broadcast_async
            print(f"WebSocket client disconnected from stream {self.stream_id} from {client_addr} (remaining clients: {len(self.clients)})")
    async def _run_async(self):
        async with websockets.serve(
            self._handler,
            "0.0.0.0",
            self.port,
            max_size=None, # important for MPEG-TS
            max_queue=1,
        ):
            print(f"WebSocketBroadcaster {self.stream_id} listening on port {self.port}")
            self._loop_ready.set()
            await asyncio.Future() # run forever

    async def _broadcast_async(self, data: bytes):
        if not self.clients:
            return
        
        # Send to each client individually, handling exceptions
        clients_to_remove = []
        for client in list(self.clients):
            # Check if client is still open before attempting to send
            if hasattr(client, 'closed') and client.closed:
                clients_to_remove.append(client)
                continue
                
            try:
                await client.send(data)
            except Exception as e:
                # Only log ConnectionClosedError, not normal closes
                if "ConnectionClosedError" in type(e).__name__:
                    if not hasattr(self, '_send_error_count'):
                        self._send_error_count = 0
                    self._send_error_count += 1
                    if self._send_error_count % 100 == 1:
                        print(f"WebSocket send error on stream {self.stream_id}: {type(e).__name__}: {e} (count: {self._send_error_count})")
                # Mark client for removal regardless of exception type
                clients_to_remove.append(client)
        
        # Clean up disconnected clients
        for client in clients_to_remove:
            self.clients.discard(client)  # Use discard to avoid KeyError if already removed
            # Don't try to close already-closed connections
            if not (hasattr(client, 'closed') and client.closed):
                try:
                    await client.close()
                except Exception:
                    pass

    def broadcast(self, data: bytes):
        if not self.running:
            return
        if not self.loop or not self.clients:
            return
        try:
            asyncio.run_coroutine_threadsafe(
                self._broadcast_async(data),
                self.loop,
            )
        except Exception as e:
            print(f"Error scheduling broadcast for stream {self.stream_id}: {e}")

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        async def runner():
            print(f"WebSocketBroadcaster {self.stream_id} listening on port {self.port}")
            try:
                # Custom process_request to suppress handshake errors
                async def process_request(connection, request):
                    # Accept all connections - let handler deal with issues
                    return None
                
                async with websockets.serve(
                    self._handler,
                    "0.0.0.0",
                    self.port,
                    max_size=None,
                    max_queue=1,
                    process_request=process_request,
                    logger=None,  # Suppress websockets library logging
                    ping_interval=20,  # Send ping every 20 seconds
                    ping_timeout=10,  # Close connection if no pong after 10 seconds
                    close_timeout=5  # Timeout for close handshake
                    ):
                    print(f"WebSocketBroadcaster {self.stream_id} ready on port {self.port}")
                    self._loop_ready.set()
                    await asyncio.Future() # run forever
            except Exception as e:
                print(f"WebSocketBroadcaster {self.stream_id} failed to start on port {self.port}: {e}")
                self._loop_ready.set() # still set to avoid deadlocks

        self.loop.run_until_complete(runner())
        self.loop.run_forever()

    def stop(self):
        self.running = False
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)