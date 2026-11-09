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
**never hang, never retry blindly, and never fail silently**.

## Contents

- [Why this library](#why-this-library)
- [Requirements and limits](#requirements-and-limits)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Connecting](#connecting)
- [Opening positions and limit orders](#opening-positions-and-limit-orders)
  - [Stops: SL and TP](#stops-sl-and-tp)
  - [Volumes, prices and comments](#volumes-prices-and-comments)
- [Closing and cancelling](#closing-and-cancelling)
  - [Magic numbers: whose trades a call touches](#magic-numbers-whose-trades-a-call-touches)
  - [Symbol and ticket](#symbol-and-ticket)
  - [One bot per account and magic 0](#one-bot-per-account-and-magic-0)
  - [Netting accounts](#netting-accounts)
- [Reading positions and orders](#reading-positions-and-orders)
- [Results and errors](#results-and-errors)
  - [Error kinds](#error-kinds)
  - [Retries](#retries)
  - [Batch failures](#batch-failures)
- [Logging](#logging)
- [Calling MetaTrader5 functions directly](#calling-metatrader5-functions-directly)
- [Migrating from 2.x](#migrating-from-2x)
- [Before trading real money](#before-trading-real-money)
- [Architecture and decisions (ADR)](#architecture-and-decisions-adr)
- [Development](#development)
- [License](#license)

Links to the other documents point to GitHub. On PyPI the Contents entries
above do not jump to their sections; read this page on
[GitHub](https://github.com/Akinzou/MetaTrader5-Python#contents) for that.

Other documents: [CHANGELOG.md](https://github.com/Akinzou/MetaTrader5-Python/blob/master/CHANGELOG.md) ·
[MIGRATION.md](https://github.com/Akinzou/MetaTrader5-Python/blob/master/MIGRATION.md) · [docs/architecture.md](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/architecture.md) ·
[docs/adr](https://github.com/Akinzou/MetaTrader5-Python/tree/master/docs/adr)

## Why this library

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
- **Close-all touches only your bot's magic.** `close_positions()` and
  `cancel_pending_orders()` act on the trader's own magic number unless told
  otherwise. With the default `magic=0` that includes manual trades: set your
  own `magic` ([details](#one-bot-per-account-and-magic-0)).
- **SL/TP as prices or distances in points.**
- **2.x compatible.** The old `Broker` class still works (deprecated).

## Requirements and limits

- **Windows** with a MetaTrader 5 terminal installed: the official
  `MetaTrader5` package is Windows-only. Python **3.10+**.
- **Algo Trading** must be enabled in the terminal. Without it every order
  fails with `ALGO_TRADING_DISABLED`. The library does not toggle it for you
  ([ADR 0004](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/adr/0004-no-gui-automation.md)).
- **One connection per process.** The official package keeps a single global
  terminal session, so a second `connect()` (or its failed login) affects the
  first. Run one process per account.
- **Thread-safe within the library.** Every terminal call holds one
  process-wide lock, so a threaded webhook server can share a `Trader`
  ([ADR 0009](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/adr/0009-one-lock-per-process.md)). The MT5 functions
  re-exported through `PythonMetaTrader5` hold it for each single call (a pair
  such as `order_send` + `last_error` is not atomic). Calls you make to the
  `MetaTrader5` module directly bypass it.

## Installation

```bash
pip install PythonMetaTrader5
```

To stay on the old API: `pip install "PythonMetaTrader5<3"`.

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

    trader.close_positions("EURUSD")  # only this bot's (magic 1001) positions
```

## Connecting

```python
connect(login, password, server, *, path=None, timeout_ms=60000, magic=0,
        deviation=10, retry=None) -> Result[Trader, TradeError]
```

| Argument | Meaning |
|---|---|
| `login` | Account number: a positive integer or a string of ASCII digits. `True`, `12345678.9` and similar values are rejected, not coerced |
| `password`, `server` | As in the terminal's login dialog, e.g. `"MetaQuotes-Demo"` |
| `path` | Path to `terminal64.exe` when more than one terminal is installed |
| `timeout_ms` | How long the terminal may take to start and log in |
| `magic` | The bot's own magic number, an integer from 0 to 2\*\*64-1. Every order is tagged with it, and close-all/cancel-all act only on it ([see below](#magic-numbers-whose-trades-a-call-touches)). Anything else, `None` included, returns `Err(INVALID_ARGUMENT)` |
| `deviation` | Maximum accepted slippage in points for market orders |
| `retry` | A `RetryPolicy` ([see Retries](#retries)) |

`connect()` never raises for a failed login: it returns
`Err(TradeError(CONNECTION_FAILED, ...))`. A `Trader` is a context manager;
`with trader:` calls `shutdown()` on exit.

## Opening positions and limit orders

| `Trader` method | Returns |
|---|---|
| `open_position(symbol, side, volume, *, sl=None, tp=None, price=None, comment=None)` | `Result[TradeReceipt, TradeError]` |
| `place_limit_order(symbol, side, volume, price, *, sl=None, tp=None, comment=None)` | `Result[TradeReceipt, TradeError]` |
| `close_positions(symbol=None, *, ticket=None, magic=<own>, comment=None)` | `Result[list[TradeReceipt], BatchFailure]` |
| `cancel_pending_orders(symbol=None, *, magic=<own>, kind=None)` | `Result[list[TradeReceipt], BatchFailure]` |
| `positions(symbol=None, *, ticket=None, magic=None)` | `Result[list[Position], TradeError]` |
| `pending_orders(symbol=None, *, magic=None, kind=None)` | `Result[list[PendingOrder], TradeError]` |
| `shutdown()` | `None` |

- `side`: `Side.BUY` / `Side.SELL`, or the strings `"buy"`, `"sell"`, `"long"`,
  `"short"`.
- A market order is built from the **current** quote; `price=` sends it once at
  that price instead.
- The filling mode comes from the symbol's allowed modes (FOK, then IOC, then
  RETURN); limit orders on exchange-execution symbols use RETURN
  ([ADR 0007](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/adr/0007-filling-and-price-grid.md)).

### Stops: SL and TP

- A float is an **absolute price**; `Stop.points(n)` is a distance of `n`
  points from the entry price (`Stop.at_price(p)` is the explicit form).
- For limit orders the distance is measured from the limit price, and for a
  market order with an explicit `price` from that price.
- Pass `None` for no stop. A float stop that is zero, negative or not finite is
  rejected (`INVALID_STOPS`): MT5 would read 0 as "no stop"
  ([ADR 0008](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/adr/0008-refuse-values-mt5-misreads.md)).
- `Stop.points()` / `Stop.at_price()` raise `ValueError` unless the value is a
  positive finite number (bool and str included); the sign of a points distance
  is ignored. A `kind` that is not a `StopKind` raises `TypeError`.
- A stop that resolves outside the tick grid's range, or to zero or below, is
  `INVALID_STOPS` when the order is built.
- For a value that may be bad at runtime, such as an ATR that is NaN during
  warm-up, use `Stop.parse(value, StopKind.POINTS)`, which returns `Ok(stop)` /
  `Err(INVALID_STOPS)` instead of raising.

### Volumes, prices and comments

- Amounts may be `int`, `float`, `Decimal` or numpy scalars; `bool` and strings
  are refused (the deprecated `Broker` still converts numeric strings).
- Volumes are checked against the symbol's min, max and step before sending
  (`INVALID_VOLUME`). Prices snap to the symbol's tick size, not just `digits`,
  so symbols with a tick of 0.25 work.
- `comment`: at most 29 UTF-16 units: 29 characters, but characters outside the
  BMP, such as most emoji, count as 2 (combined emoji more). The `MetaTrader5`
  package refuses 30 or more (measured on 5.0.6231; its docs say 31). Longer
  comments, and comments that are not `str`, are rejected before sending
  (`INVALID_ARGUMENT`), not truncated.

## Closing and cancelling

### Magic numbers: whose trades a call touches

A magic number tags every order a bot sends. MT5 gives trades opened by hand
magic **0**. Decision and reasoning:
[ADR 0011](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/adr/0011-close-all-defaults-to-own-magic.md).

| Call | Acts on |
|---|---|
| `close_positions()` / `cancel_pending_orders()` | Only the trader's own magic (the one given to `connect()`) |
| `...(magic=None)` | Still only the own magic: a `None` from a missing config key cannot widen the call |
| `...(magic=7)` | Only magic 7 |
| `...(magic=ANY_MAGIC)` | Every magic on the account, manual trades included |
| `close_positions(ticket=t)` | Position `t`, whatever its magic: you named it. With `magic=` too, `t` closes only if its magic matches |
| `positions()` / `pending_orders()` | Every magic by default: a read cannot close anything |

A magic must be an integer from 0 to 2\*\*64-1 (MT5's ulong). `"42"`, `True`,
`1.5`, `-1` and `2**64` are refused as `INVALID_ARGUMENT` instead of matching
nothing and reporting an empty success.

```python
from PythonMetaTrader5 import ANY_MAGIC

trader.close_positions()                   # this bot's positions only
trader.close_positions(magic=ANY_MAGIC)    # the whole account
```

### Symbol and ticket

- `symbol` limits a call to that symbol exactly: `close_positions("EURGBP")`
  never touches a EURUSD position, also with `magic=ANY_MAGIC`. The adapter
  re-checks the symbol of every position MT5 returns.
- `ticket` takes precedence over `symbol`, as in 2.x:
  `close_positions("EURGBP", ticket=t)` closes position `t` even if it is on
  EURUSD.
- `ticket` must be a positive integer; `0`, `True` or `"7"` are rejected (0 may
  mean "no filter" to MT5). An empty string `""` as symbol is rejected too: a
  missing webhook field must not mean "every symbol".
- `cancel_pending_orders(kind=PendingKind.LIMIT)` limits a cancel to one order
  type (`LIMIT`, `STOP`, `STOP_LIMIT`).
- Each position is closed on its own symbol with its own spec, and a symbol
  with broken data can still be closed.

### One bot per account and magic 0

`connect()` keeps `magic=0` as its default, so a bot that is alone on its
account works without setting one. The cost: manual trades share magic 0, so
such a bot's close-all also closes manual positions and cancels manual pending
orders. Whenever a defaulted close/cancel of a magic-0 trader affects
something, the library logs a warning:

```
trader magic is 0, which manual trades share: this close/cancel includes them; set magic at connect(), or pass magic=0 to confirm
```

- Bot alone on the account and the behaviour is intended: pass `magic=0`
  explicitly (`close_positions(magic=0)`) and the warning is not logged.
- Bot next to manual trading or other bots: give it its own magic in
  `connect(..., magic=1001)`.

### Netting accounts

On a netting account one position per symbol collects every deal and keeps the
magic of the deal that opened it, so merged volume cannot be told apart by
magic. A bot's deal that merges into a manual position is not "own"; a manual
deal that merges into the bot's position is. When a defaulted close/cancel
matches nothing while items with other magics are in scope, the library logs
how many it left open, so `Ok([])` never reads as "flat" in silence. If that
extra listing fails, the warning says it could not check.

## Reading positions and orders

- `Position`: `ticket`, `symbol`, `side`, `volume`, `price_open`, `sl`, `tp`
  (`None` when not set), `price_current`, `profit`, `swap`, `time`, `magic`,
  `comment`, and MT5's `identifier`, `reason`, `time_msc`, `time_update`,
  `time_update_msc`, `external_id`.
- `PendingOrder`: `ticket`, `symbol`, `side`, `kind` (`PendingKind`), `volume`,
  `price`, `magic`, `comment`.
- `TradeReceipt` (the broker's answer): `retcode`, `deal`, `order`, `volume`,
  `price`, `bid`, `ask`, `comment`, `request_id`, `retcode_external`. For a
  close, `order` / `deal` are the IDs of the closing deal, not the position
  ticket.
- An empty account is `Ok([])`; a terminal failure is `Err(TERMINAL_ERROR)`,
  never an empty list.

## Results and errors

Expected failures are values, not exceptions
([ADR 0002](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/adr/0002-result-at-boundaries.md)): every call returns `Ok(...)`
or `Err(...)`. Exceptions are reserved for programming errors such as
`RetryPolicy(attempts=0)` or `Stop.points("x")`.

`TradeError(kind, message, retcode=None, receipt=None, ticket=None)`. The
`receipt` carries the broker's raw answer when there was one; `ticket` names the
position/order in a batch.

### Error kinds

| `ErrorKind` | Meaning | What to do |
|---|---|---|
| `INVALID_ARGUMENT`, `INVALID_VOLUME`, `INVALID_PRICE`, `INVALID_STOPS` | Refused before sending, or by the server for the same reason | Fix the input; a resend gives the same answer |
| `INVALID_FILLING` | The server refused the filling mode the library chose from the symbol's flags (10030) | Nothing to fix in your call: escalate to the broker; a resend gives the same answer |
| `NO_MONEY`, `LIMIT_REACHED` | Margin or a broker limit | Do not resend unchanged |
| `MARKET_CLOSED`, `TRADE_DISABLED` | The symbol cannot be traded now | Wait or skip |
| `ALGO_TRADING_DISABLED` | Algo Trading is off in the terminal (10027) or on the server (10026) | 10027: enable it in the terminal. 10026: the broker or account forbids it; contact the broker |
| `PARTIAL_FILL` | Part of the volume executed | Check `positions()`; never re-sent |
| `OUTCOME_UNKNOWN` | Timeout, lost connection, or a queued market deal | **Check `positions()` before anything else**: the order may be live |
| `RETRIES_EXHAUSTED` | Requotes/price changes outlasted the retry policy | Retry later with a fresh decision |
| `REJECTED` | Any other server refusal (also unknown retcodes) | Read `message` and `retcode` |
| `SYMBOL_NOT_FOUND`, `NO_PRICE` | Unknown symbol, or no quote | Check the symbol name and market data |
| `BROKEN_SYMBOL_DATA` | The terminal's symbol data cannot price an order (point 0, NaN tick size, volume step 0) | Escalate; a resend gives the same answer. Closing still works |
| `TERMINAL_ERROR`, `CONNECTION_FAILED` | The terminal or the login failed | Check the terminal and credentials |

### Retries

[ADR 0003](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/adr/0003-bounded-retries.md):

| Server answer | What happens |
|---|---|
| market deal (entry or close): done | `Ok(receipt)` |
| pending order: placed or done | `Ok(receipt)` |
| market deal: partial fill | `PARTIAL_FILL` with the receipt; part of the deal exists, never re-sent |
| market deal: placed (queued, not executed) | `OUTCOME_UNKNOWN` with the receipt, never re-sent |
| requote, price changed, no quotes, too many requests | retried with a fresh quote, up to `RetryPolicy.attempts` (default 3, 0.5 s apart), then `RETRIES_EXHAUSTED` |
| timeout, no connection, or `order_send` lost in IPC | `OUTCOME_UNKNOWN`, never retried: check `positions()` first |
| anything else | the matching `ErrorKind`, returned at once |
| refused before sending: no quote yet (`NO_PRICE`, e.g. a symbol just added to Market Watch) | waited for and rebuilt up to `RetryPolicy.attempts`, then `NO_PRICE`; nothing was sent |
| refused before sending: anything else | the matching `ErrorKind`, returned at once; nothing was sent |

```python
from PythonMetaTrader5 import RetryPolicy, connect

connect(..., retry=RetryPolicy(attempts=5, delay_seconds=0.2))
```

### Batch failures

`close_positions()` and `cancel_pending_orders()` try every matching item and
return `Ok(receipts)` only when all succeeded (`Ok([])` when nothing matched).
Otherwise they return `Err(BatchFailure)`:

- `BatchFailure.succeeded`: receipts of the items that worked.
- `BatchFailure.errors`: one `TradeError` per item that failed, with
  `TradeError.ticket` naming it.
- When the call fails before trying any item (an invalid `magic` or `comment`,
  or the listing itself fails), `succeeded` is empty and the single error has
  `ticket=None`.
- A failed item is not necessarily still open: `OUTCOME_UNKNOWN` may have
  closed it and `PARTIAL_FILL` closed part of it. Read `positions()` before
  sending again.

```python
from PythonMetaTrader5 import ErrorKind

match trader.close_positions("EURUSD"):
    case Ok(receipts):
        print("closed", len(receipts))
    case Err(failure):
        for error in failure.errors:
            if error.ticket is None:
                print("nothing tried:", error.kind, error.message)
            elif error.kind in (ErrorKind.OUTCOME_UNKNOWN, ErrorKind.PARTIAL_FILL):
                print("check positions():", error.ticket, error.kind)
            else:
                # REJECTED also covers "position already closed" (10036).
                print("not closed by this call:", error.ticket, error.kind, error.message)
```

## Logging

The library logs through the standard `logging` module under the
`PythonMetaTrader5` logger and never configures handlers itself
([ADR 0005](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/adr/0005-stdlib-logging.md)). Without any logging
configuration, warnings and errors still reach stderr. The login and server are
logged on connect; the account owner's name and balance are not.

## Calling MetaTrader5 functions directly

As in 2.x, the `MetaTrader5` functions and constants are reachable through this
package, loaded lazily ([ADR 0010](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/adr/0010-keep-the-metatrader5-re-export.md)):

```python
from PythonMetaTrader5 import *

info = symbol_info("EURUSD")
print(ORDER_TYPE_BUY)
```

Names defined by this library win over MT5's (our `Tick` over MT5's struct).

## Migrating from 2.x

`from PythonMetaTrader5 import Broker` keeps working and emits a
`DeprecationWarning` ([ADR 0006](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/adr/0006-legacy-facade.md)). `Broker`
keeps 2.x behaviour where it was safe: `Close` and `CancelOrders` still act on
every magic. Several 2.x behaviours were unsafe and changed: endless retries,
`sl=0` as "no stop", Ctrl+E automation, fixed filling modes and more. Read
[MIGRATION.md](https://github.com/Akinzou/MetaTrader5-Python/blob/master/MIGRATION.md) before upgrading a bot that trades real money; it
also maps the main `Broker` calls to their `Trader` equivalents.

## Before trading real money

- Run your bot on a **demo** account first. The library's own demo tests need
  a source checkout ([Development](#development)); they are not in the wheel.
- Give every bot its own `magic` unless it is alone on the account.
- Treat `OUTCOME_UNKNOWN` as "maybe filled": read `positions()` before sending
  again.
- Check `Err` on every call. A refused close leaves the position open; an
  `OUTCOME_UNKNOWN` or `PARTIAL_FILL` close may have closed all or part of it,
  so read `positions()` before acting again.
- Trading carries risk; this software comes without any warranty.

## Architecture and decisions (ADR)

Clean Architecture with Ports & Adapters: `domain/` holds the trading rules,
`application/` the use cases (`Trader`), `adapters/` the only code that talks
to MetaTrader 5. Details: [docs/architecture.md](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/architecture.md).

| ADR | Decision |
|---|---|
| [0001](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/adr/0001-ports-only-at-process-boundaries.md) | Ports only at process boundaries |
| [0002](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/adr/0002-result-at-boundaries.md) | Result values at boundaries, exceptions for programming errors |
| [0003](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/adr/0003-bounded-retries.md) | Bounded retries, never on an unknown outcome |
| [0004](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/adr/0004-no-gui-automation.md) | No GUI automation for Algo Trading |
| [0005](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/adr/0005-stdlib-logging.md) | Standard logging, no NullHandler |
| [0006](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/adr/0006-legacy-facade.md) | Keep a 2.x `Broker` facade |
| [0007](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/adr/0007-filling-and-price-grid.md) | Filling mode from the symbol, prices on the tick grid |
| [0008](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/adr/0008-refuse-values-mt5-misreads.md) | Refuse input that MT5 would quietly read as something else |
| [0009](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/adr/0009-one-lock-per-process.md) | One lock per process around terminal calls |
| [0010](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/adr/0010-keep-the-metatrader5-re-export.md) | Keep re-exporting the MetaTrader5 namespace, lazily |
| [0011](https://github.com/Akinzou/MetaTrader5-Python/blob/master/docs/adr/0011-close-all-defaults-to-own-magic.md) | Close-all and cancel-all default to the trader's own magic |

## Development

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
ruff check src tests scripts && ruff format --check src tests scripts
mypy
pytest --cov
python scripts/check_file_length.py
```

`tests/contract` compares the unit-test fakes with the installed `MetaTrader5`
package and is skipped where it is not installed (anywhere but Windows).
Integration tests trade on a **demo** account and are skipped unless
`MT5_LOGIN`, `MT5_PASSWORD` and `MT5_SERVER` are set (they refuse to run on a
live account): `pytest -m integration`.

## License

[CC BY-NC 4.0](https://github.com/Akinzou/MetaTrader5-Python/blob/master/LICENSE). Trading carries risk; this software comes without any
warranty.
