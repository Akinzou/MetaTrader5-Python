"""Composition root: wires the real adapters into a Trader."""

from __future__ import annotations

import logging

from PythonMetaTrader5.adapters.mt5_terminal import MetaTrader5Terminal
from PythonMetaTrader5.adapters.system_clock import SystemClock
from PythonMetaTrader5.application.execution import RetryPolicy
from PythonMetaTrader5.application.ports import Credentials, parse_login
from PythonMetaTrader5.application.trader import Trader
from PythonMetaTrader5.domain.errors import ErrorKind, TradeError
from PythonMetaTrader5.domain.inputs import own_magic
from PythonMetaTrader5.result import Err, Ok, Result

log = logging.getLogger("PythonMetaTrader5")


def connect(
    login: int | str,
    password: str,
    server: str,
    *,
    path: str | None = None,
    timeout_ms: int = 60_000,
    magic: int = 0,
    deviation: int = 10,
    retry: RetryPolicy | None = None,
) -> Result[Trader, TradeError]:
    """Start (or attach to) the MT5 terminal, log in, and return a ready Trader."""
    account = parse_login(login)
    if account is None:
        return Err(
            TradeError(
                ErrorKind.INVALID_ARGUMENT, f"login must be a positive integer, got {login!r}"
            )
        )
    own = own_magic(magic)
    if isinstance(own, Err):
        return own
    loaded = MetaTrader5Terminal.load()
    if isinstance(loaded, Err):
        return loaded
    terminal = loaded.value
    credentials = Credentials(account, str(password), str(server), path, timeout_ms)
    connected = terminal.connect(credentials)
    if isinstance(connected, Err):
        return connected
    # Login and server only: account_info() also carries the owner's name and
    # balance, which do not belong in application logs.
    log.info("connected to %s as %s", server, account)
    return Ok(Trader(terminal, SystemClock(), magic=own.value, deviation=deviation, retry=retry))
