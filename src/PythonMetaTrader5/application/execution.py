"""Sending a request with a bounded, outcome-aware retry loop."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace

from PythonMetaTrader5.application.ports import Clock, Terminal
from PythonMetaTrader5.domain.errors import ErrorKind, TradeError
from PythonMetaTrader5.domain.market import TradeReceipt
from PythonMetaTrader5.domain.requests import CancelRequest, OrderRequest
from PythonMetaTrader5.domain.retcodes import Outcome, classify, error_for
from PythonMetaTrader5.result import Err, Result

log = logging.getLogger("PythonMetaTrader5")

RequestFactory = Callable[[], Result[OrderRequest | CancelRequest, TradeError]]


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    attempts: int = 3
    delay_seconds: float = 0.5

    def __post_init__(self) -> None:
        # Misconfiguration is a programming error, not a market outcome, so it
        # fails loudly at construction instead of travelling as a Result.
        if self.attempts < 1 or self.delay_seconds < 0:
            raise ValueError(f"invalid retry policy: {self}")


def execute(
    terminal: Terminal, clock: Clock, build: RequestFactory, policy: RetryPolicy
) -> Result[TradeReceipt, TradeError]:
    """Rebuild and send the request until it succeeds, fails, or attempts run out.

    The request is rebuilt on every attempt so a requote is answered with the
    current price instead of re-sending the stale one.
    """
    last: TradeReceipt | None = None
    for attempt in range(1, policy.attempts + 1):
        request = build()
        if isinstance(request, Err):
            # Nothing was sent, so waiting is safe; a symbol just added to Market
            # Watch typically has no quote for the first few hundred milliseconds.
            if request.error.kind is ErrorKind.NO_PRICE and attempt < policy.attempts:
                clock.sleep(policy.delay_seconds)
                continue
            return request
        sent = terminal.send(request.value)
        if isinstance(sent, Err):
            return sent
        last = sent.value
        outcome = classify(last.retcode)
        if outcome is Outcome.SUCCESS:
            return sent
        if outcome is Outcome.FAIL:
            return Err(replace(error_for(last.retcode), receipt=last))
        log.warning("retcode %s on attempt %s/%s", last.retcode, attempt, policy.attempts)
        if attempt < policy.attempts:
            clock.sleep(policy.delay_seconds)
    if last is None:  # pragma: no cover - range(1, attempts + 1) is never empty
        raise AssertionError("retry loop ran zero times")
    return Err(
        TradeError(
            ErrorKind.RETRIES_EXHAUSTED,
            f"gave up after {policy.attempts} attempts: {error_for(last.retcode).message}",
            retcode=last.retcode,
            receipt=last,
        )
    )
