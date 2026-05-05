import queue


class BackpressureQueue:
    """Queue that drops oldest frames when full (backpressure-safe)."""

    def __init__(self, max_queue_size: int = 10000, queue_timeout_ms: int = 500):
        self.queue = queue.Queue(maxsize=max_queue_size)
        self.timeout_s = queue_timeout_ms / 1000.0
        self.dropped_frames = 0

    def put(self, item):
        try:
            self.queue.put_nowait(item)
        except queue.Full:
            try:
                self.queue.get_nowait()
                self.dropped_frames += 1
            except queue.Empty:
                pass

            try:
                self.queue.put_nowait(item)
            except queue.Full:
                self.dropped_frames += 1

    def get(self):
        return self.queue.get(timeout=self.timeout_s)

    def empty(self):
        return self.queue.empty()

    def qsize(self):
        return self.queue.qsize()
