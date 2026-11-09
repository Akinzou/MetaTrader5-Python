"""2.x argument conventions translated into 3.x values.

Split out of broker.py (300-line limit); everything here is pure.
"""

from __future__ import annotations

import logging
from typing import Any

from PythonMetaTrader5.domain.stops import Stop
from PythonMetaTrader5.result import Err, Ok, Result

log = logging.getLogger("PythonMetaTrader5.legacy")


def number(value: Any) -> Any:
    """Convert numeric strings with float() as 2.x did, raising on garbage as it did.

    Only strings are converted: float(True) would turn a stray bool into one
    lot, so every other type goes on unchanged and is checked by the Trader.
    """
    return float(value) if isinstance(value, str) else value


def legacy_stop(value: Any, kind: str) -> Result[Stop | None, str]:
    if value is None:
        return Ok(None)
    match (kind or "absolute").lower():
        case "absolute":
            return Ok(Stop.at_price(value))
        case "offset":
            return Ok(Stop.points(value))
        case other:
            # 2.x opened the position with neither SL nor TP here.
            log.error("invalid stop type %r (use 'absolute' or 'offset')", other)
            return Err(other)


def no_ticket(ticket: int | None) -> bool:
    if ticket is None:
        return True
    # 2.x forwarded it as `position` on an opening deal, which on hedging
    # accounts turns an opposite-side entry into a close of that position.
    log.error("the ticket argument is not supported for entries; use Close(ticket=...)")
    return False
