# PythonMetaTrader5

[![CI](https://github.com/Akinzou/MetaTrader5-Python/actions/workflows/ci.yml/badge.svg)](https://github.com/Akinzou/MetaTrader5-Python/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pythonmetatrader5)](https://pypi.org/project/PythonMetaTrader5/)
![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-CC_BY--NC_4.0-lightgrey.svg)
[![PyPI Downloads](https://static.pepy.tech/badge/pythonmetatrader5)](https://pepy.tech/projects/pythonmetatrader5)
[![Discord](https://img.shields.io/badge/Discord-join-5865F2?logo=discord&logoColor=white)](https://discord.gg/BARYa55KS8)

A safe, typed trading layer over the official
[`MetaTrader5`](https://pypi.org/project/MetaTrader5/) Python package.

Built for bots (webhook executors, signal followers) where a trading call must
**never hang, never retry blindly, and never fail silently**:

- **Every trading call returns.** Requotes are retried a bounded number of times
  with a fresh quote; everything else comes back immediately as a typed error.
  (The deprecated `Broker.login(ToEffect=True)` is the one exception: as in
  2.x, it keeps trying until the login works.)
- **No silent defaults.** Values that MT5 would quietly read as something else
  are refused before sending: `sl=0` ("no stop"), `ticket=0` (possibly "no
  filter"), `volume=True` (one lot), NaN and infinities.
- **No double fills.** Timeouts and lost connections are never auto-retried:
  the order may already be live.
- **Typed results.** `Ok(receipt)` or `Err(TradeError)` with an `ErrorKind`
  (`MARKET_CLOSED`, `NO_MONEY`, `INVALID_STOPS`, ...) instead of magic numbers.
- **Correct prices and lots.** Prices snap to the symbol's tick grid, volumes
  are checked against min/max/step, the filling mode is chosen from the symbol.
- **Magic numbers.** Tag your bot's trades and close/cancel only those.
- **SL/TP as prices or distances in points.**
- **2.x compatible.** The old `Broker` class still works (deprecated).

> One connection per process: the official package keeps a single global
> terminal session, so a second `connect()` (or its failed login) affects the
> first. Run one process per account.
>
> Thread-safe within the library: every terminal call holds one process-wide
> lock, so a threaded webhook server can share a `Trader`. Calls you make to
> the `MetaTrader5` module directly bypass that lock.
>
> Requires Windows with a MetaTrader 5 terminal installed (the official
> `MetaTrader5` package is Windows-only). Enable **Algo Trading** in the terminal.

## Installation

```bash
pip install PythonMetaTrader5
```

## Quick start

```python
from PythonMetaTrader5 import Err, Ok, Side, Stop, connect

match connect(12345678, "password", "MetaQuotes-Demo", magic=1001):
    case Err(error):
        raise SystemExit(f"cannot connect: {error}")
    case Ok(trader):
        pass

with trader:  # shuts the terminal connection down on exit
    result = trader.open_position(
        "EURUSD", Side.BUY, 0.10,
        sl=Stop.points(1000),  # 1000 points below the entry price
        tp=1.12500,            # a plain float is an absolute price
        comment="webhook #42",
    )
    match result:
        case Ok(receipt):
            print("filled at", receipt.price, "deal", receipt.deal)
        case Err(error):
            print("not opened:", error.kind, error.message)

    trader.close_positions("EURUSD", magic=1001)  # only this bot's positions
```

## API

`connect(login, password, server, *, path=None, timeout_ms=60000, magic=0,
deviation=10, retry=None) -> Result[Trader, TradeError]`

`login` must be a positive integer or a string of ASCII digits; `True`,
`12345678.9` and similar values are rejected rather than coerced.

| `Trader` method | Returns |
|---|---|
| `open_position(symbol, side, volume, *, sl=None, tp=None, price=None, comment=None)` | `Result[TradeReceipt, TradeError]` |
| `place_limit_order(symbol, side, volume, price, *, sl=None, tp=None, comment=None)` | `Result[TradeReceipt, TradeError]` |
| `close_positions(symbol=None, *, ticket=None, magic=None, comment=None)` | `Result[list[TradeReceipt], BatchFailure]` |
| `cancel_pending_orders(symbol=None, *, magic=None, kind=None)` | `Result[list[TradeReceipt], BatchFailure]` |
| `positions(symbol=None, *, ticket=None, magic=None)` | `Result[list[Position], TradeError]` |
| `pending_orders(symbol=None, *, magic=None, kind=None)` | `Result[list[PendingOrder], TradeError]` |
| `shutdown()` | `None` |

- `side`: `Side.BUY` / `Side.SELL`, or the strings `"buy"`, `"sell"`, `"long"`, `"short"`.
- `sl` / `tp`: a float is an **absolute price**; `Stop.points(n)` is a distance
  of `n` points from the entry price (`Stop.at_price(p)` is the explicit form).
  For limit orders the distance is measured from the limit price, and for a
  market order with an explicit `price` from that price. Zero, negative and
  non-finite stops are rejected (`INVALID_STOPS`); pass `None` for no stop.
- `price` (market orders): send at this price once instead of the live quote.
- `comment`: at most 31 characters (the terminal's limit). Longer comments are
  rejected, not truncated.
- **`close_positions()` and `cancel_pending_orders()` without arguments act on
  the whole account**, including manual trades. A bot should always pass its
  `magic` (and a symbol); an empty string `""` is rejected.
- `BatchFailure.errors` names every position/order that failed
  (`TradeError.ticket`). `BatchFailure.succeeded` holds the receipts of the
  ones that worked; their `order` / `deal` are the IDs of the closing deal, not
  the position ticket.
- `ticket` must be a positive integer; `0`, `True` or `"7"` are rejected.

### Errors

`TradeError(kind, message, retcode=None, receipt=None, ticket=None)`. The
`receipt` carries the broker's raw answer when there was one. Retry policy:

| Server answer | What happens |
|---|---|
| market deal (entry or close): done | `Ok(receipt)` |
| pending order: placed or done | `Ok(receipt)` |
| market deal: partial fill | `PARTIAL_FILL` with the receipt; part of the deal exists, never re-sent |
| market deal: placed (queued, not executed) | `OUTCOME_UNKNOWN` with the receipt, never re-sent |
| requote, price changed, no quotes, too many requests | retried with a fresh quote, up to `RetryPolicy.attempts` (default 3, 0.5 s apart), then `RETRIES_EXHAUSTED` |
| timeout, no connection, or `order_send` lost in IPC | `OUTCOME_UNKNOWN`, never retried: check `positions()` first |
| anything else | the matching `ErrorKind`, returned at once |

```python
from PythonMetaTrader5 import RetryPolicy, connect

connect(..., retry=RetryPolicy(attempts=5, delay_seconds=0.2))
```

### Logging

The library logs through the standard `logging` module under the
`PythonMetaTrader5` logger and never configures handlers itself. Without any
logging configuration, warnings and errors still reach stderr.

## Migrating from 2.x

`from PythonMetaTrader5 import Broker` keeps working and emits a
`DeprecationWarning`. Several 2.x behaviours were unsafe and changed: see
[MIGRATION.md](MIGRATION.md).

## Development

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
ruff check src tests scripts && ruff format --check src tests scripts
mypy
pytest --cov
```

`tests/contract` compares the unit-test fakes with the installed `MetaTrader5`
package and is skipped where it is not installed (anywhere but Windows).
Integration tests trade on a **demo** account and are skipped unless
`MT5_LOGIN`, `MT5_PASSWORD` and `MT5_SERVER` are set (they refuse to run on a
live account): `pytest -m integration`.

Architecture and decisions: [docs/architecture.md](docs/architecture.md),
[docs/adr](docs/adr).

## License

[CC BY-NC 4.0](LICENSE). Trading carries risk; this software comes without any
warranty.
