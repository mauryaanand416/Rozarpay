import threading
import time
from collections import deque


class EventBus:
    def __init__(self, maxlen: int = 300):
        self._buffer: deque = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._counter = 0
        self._event = threading.Event()

    def publish(self, payload: dict) -> int:
        with self._lock:
            self._counter += 1
            item = {"id": self._counter, "at": time.time(), "data": payload}
            self._buffer.append(item)
        self._event.set()
        return self._counter

    def since(self, last_id: int) -> list[dict]:
        with self._lock:
            return [i for i in self._buffer if i["id"] > last_id]

    def wait(self, timeout: float) -> None:
        self._event.wait(timeout)
        self._event.clear()


bus = EventBus()
