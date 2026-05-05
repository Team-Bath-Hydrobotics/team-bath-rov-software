import asyncio
import threading

import cv2


class FrameWebSocketServer:
    def __init__(self, port):
        self.port = port
        self.clients = set()
        self.loop = asyncio.new_event_loop()
        self.server = None

    # -------------------------
    # Lifecycle
    # -------------------------
    def start(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._start_server())
        self.loop.run_forever()

    async def _start_server(self):
        import websockets

        self.server = await websockets.serve(
            self.handler,
            "0.0.0.0",
            self.port,
            max_size=None,
            ping_interval=20,
            ping_timeout=10,
        )
        print(f"[WS] Server started on port {self.port}")

    # -------------------------
    # Connection handler
    # -------------------------
    async def handler(self, ws):
        print("[WS] client connected")
        self.clients.add(ws)
        try:
            await ws.wait_closed()
        finally:
            self.clients.discard(ws)

    # -------------------------
    # Broadcast entry point (called from other threads)
    # -------------------------
    def broadcast(self, frame):
        jpeg = self.encode_jpeg(frame)
        if jpeg is None:
            print("[WS] JPEG encode failed")
            return
        asyncio.run_coroutine_threadsafe(self._broadcast(jpeg), self.loop)

    async def _broadcast(self, jpeg):
        dead = []

        for ws in list(self.clients):
            try:
                await ws.send(jpeg)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.clients.discard(ws)

    # -------------------------
    # Encoding
    # -------------------------
    def encode_jpeg(self, frame, quality=80):
        ok, buf = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), quality],
        )
        if not ok:
            return None
        return buf.tobytes()
