import os
import threading
import time

import psutil


class MetricsMonitor(threading.Thread):
    def __init__(self, memory_threshold):
        super().__init__(daemon=True)
        self.process = psutil.Process(os.getpid())
        self.memory_threshold = memory_threshold
        self.running = True

    def run(self):
        while self.running:
            mem = self.get_memory_mb()

            print(f"[Metrics] mem={mem:.1f}MB")

            if mem > self.memory_threshold:
                print(f"HIGH MEMORY USAGE: {mem:.1f}MB")

            time.sleep(0.5)

    def get_memory_mb(self):
        return self.process.memory_info().rss / (1024 * 1024)

    def stop(self):
        self.running = False
        self.join(timeout=1.0)
