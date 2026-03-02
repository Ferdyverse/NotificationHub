from __future__ import annotations

import hashlib
import time
from collections import deque


class DedupeCache:
    def __init__(self, window_seconds: int):
        self.window_seconds = window_seconds
        self._cache: dict[str, float] = {}

    def _cleanup(self, now: float):
        expired = [key for key, ts in self._cache.items() if now - ts > self.window_seconds]
        for key in expired:
            self._cache.pop(key, None)

    def seen_recently(self, key: str) -> bool:
        now = time.time()
        self._cleanup(now)
        if key in self._cache:
            return True
        self._cache[key] = now
        return False

    @staticmethod
    def build_key(*parts: str) -> str:
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class RateLimiter:
    def __init__(self, limit_per_min: int):
        self.limit_per_min = limit_per_min
        self._events: dict[str, deque] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        window = 60
        bucket = self._events.setdefault(key, deque())
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= self.limit_per_min:
            return False
        bucket.append(now)
        return True
