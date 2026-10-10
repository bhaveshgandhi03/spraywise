"""Small, dependency-free security helpers: rate limiting, daily LLM budget, image sniffing, headers."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from datetime import date, datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def today_ist() -> date:
    return datetime.now(IST).date()


class RateLimiter:
    """Sliding-window limiter kept in memory (fine for one small instance)."""

    def __init__(self, limit: int, window_s: int = 60) -> None:
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > self.window_s:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            # keep memory bounded
            if len(self._hits) > 5000:
                for k in [k for k, v in self._hits.items() if not v]:
                    del self._hits[k]
            return True


class DailyBudget:
    """Hard cap on paid LLM calls per day so a leaked link cannot run up a bill."""

    def __init__(self, max_calls: int) -> None:
        self.max_calls = max_calls
        self._day = today_ist()
        self._used = 0
        self._lock = threading.Lock()

    def consume(self) -> bool:
        with self._lock:
            d = today_ist()
            if d != self._day:
                self._day, self._used = d, 0
            if self._used >= self.max_calls:
                return False
            self._used += 1
            return True

    @property
    def used(self) -> int:
        return self._used


def client_key(headers, fallback: str) -> str:
    """Render and most hosts put the real client first in X-Forwarded-For."""
    fwd = headers.get("x-forwarded-for", "")
    first = fwd.split(",")[0].strip()
    return first or fallback or "unknown"


def sniff_image(data: bytes) -> str | None:
    """Return a media type only if the bytes really look like JPEG, PNG or WebP."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
        "connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(self), microphone=(), geolocation=()",
    "X-Frame-Options": "DENY",
}
