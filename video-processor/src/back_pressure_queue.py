import queue


class BackpressureQueue:
    """A queue that drops old frames if they're not consumed within the timeout"""

    def __init__(self, max_queue_size: int = 10000, queue_timeout_ms: int = 500):
        self.queue = queue.Queue(maxsize=max_queue_size)
        self.timeout_s = queue_timeout_ms / 1000.0
        self.dropped_frames = 0
        print(
            f"Backpressure Queue initialized with max size {max_queue_size} and timeout {self.timeout_s}s"
        )

    def put(self, item, timeout=None):
        """Put item in queue, dropping old items if queue is full"""
        try:
            # Try to put without blocking
            self.queue.put_nowait(item)
        except queue.Full:
            # Queue is full, drop oldest items until we can add new one
            dropped_count = 0
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                    dropped_count += 1
                except queue.Empty:
                    break

            self.dropped_frames += dropped_count
            if dropped_count % 1000 == 0:
                print(
                    f"Dropped {dropped_count} frames due to backpressure "
                    f"(total: {self.dropped_frames})"
                )

            # Now add the new item
            try:
                self.queue.put_nowait(item)
            except queue.Full:
                self.dropped_frames += 1

    def get(self, timeout=None):
        """Get item from queue with timeout"""
        timeout = timeout or self.timeout_s
        return self.queue.get(timeout=timeout)

    def empty(self):
        return self.queue.empty()
