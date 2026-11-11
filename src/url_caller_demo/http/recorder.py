"""Keep bounded, thread-safe observations for each distinct document visit.

A delayed preload beacon cannot be mistaken for the timed reload's beacon.
"""

import copy
import threading
import time
import uuid


class Recorder:
    def __init__(self, capacity=2000):
        if type(capacity) is not int or capacity < 1:
            raise ValueError("Capacity must be a positive integer.")
        self.capacity = capacity
        self.rows = {}
        self.lock = threading.Lock()

    def arrival(self, trial):
        now = time.monotonic_ns()
        visit = uuid.uuid4().hex
        if not trial:
            return visit
        with self.lock:
            if trial not in self.rows and len(self.rows) >= self.capacity:
                self.rows.pop(next(iter(self.rows)))
            row = self.rows.setdefault(trial, {"arrival_count": 0, "visits": []})
            row["arrival_count"] += 1
            row["visits"].append({"visit": visit, "arrival_ns": now})
            del row["visits"][:-4]
        return visit

    def interactive(self, trial, visit, data):
        now = time.monotonic_ns()
        with self.lock:
            for item in self.rows.get(trial, {}).get("visits", []):
                if item["visit"] == visit:
                    item.setdefault("interactive_ns", now)
                    item.setdefault("interactive_data", data)
                    return True
        return False

    def get(self, trial):
        with self.lock:
            return copy.deepcopy(self.rows.get(trial, {}))
