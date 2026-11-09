"""Wall-clock adapter for the Clock port."""

from __future__ import annotations

import time


class SystemClock:
    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)
