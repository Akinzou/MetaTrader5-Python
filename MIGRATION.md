# Migrating from 2.x to 3.0

3.0 is a rewrite. Existing code using `Broker` keeps running, but the behaviours
below changed on purpose because they were unsafe. Read this list before
upgrading a bot that trades real money.

## Requirements

- Python **3.10+** (2.x claimed 3.6+).
- `pyautogui` and `loguru` are no longer dependencies.
- Creating a `Broker` emits a `DeprecationWarning`. Test suites that run with
  `-W error` or pytest's `filterwarnings = error` must allow it, e.g.
  `filterwarnings = ["error", "ignore:Broker is deprecated:DeprecationWarning"]`.

## Behaviour changes in `Broker`

### Logging in

| 2.x | 3.0 | Why |
|---|---|---|
| The constructor called `initialize()` without credentials, then `login()`. After a failed login it went on trading on whichever account the terminal had open | A failed login shuts the terminal session down. Every method then returns `None` / `[]` / `False` and logs "not connected" until `login()` succeeds | Orders went to an account nobody asked for |
| A failed `login()` (for example as a health check) left the working session alone | A failed `login()` also shuts the session down and disables the `Broker` until a login works | After a failed login MT5's single per-process session can be left half-open, so later `initialize()` calls fail |
| Several `Broker` objects in one process each believed they had their own connection | Unchanged, but now visible: MT5 has one session per process, so one instance's failed login disconnects the others too | Run one process per account |
| `Broker(True, ...)` or `Broker(12345678.9, ...)` logged into account 1 / 12345678 | Raises `ValueError` (as a non-numeric login already did) | It traded on a different account than intended |

### Opening positions and limit orders

| 2.x | 3.0 | Why |
|---|---|---|
| `OpenPosition`, `Buy*`, `Sell*`, `BuyLimit`, `SellLimit` retried **forever** on any unknown retcode (no money, invalid volume, market closed over the weekend), sending an order every 0.5 s | Requotes are retried at most 3 times. Any other broker refusal returns at once: the receipt is returned and the error is logged | A weekend webhook blocked the bot until Monday; a rejected order was re-sent indefinitely |
| Invalid input was sent anyway and then retried forever | Refused **before sending**: the call returns `None`, not a receipt, and logs why. This covers a volume off the lot step or outside min/max, an unknown symbol, a comment over 31 characters, and the cases below. Check for `None` before reading `.retcode` | Nothing was sent, so there is no broker answer to return |
| `sl=0` / `tp=0` sent 0.0, which MT5 reads as "no stop" | Refused (returns `None`). Pass `None`, or leave the argument out, for no stop | A missing SL field in a webhook opened an unprotected position without any error |
| An unknown `sl_type` / `tp_type` (e.g. `"bogus"`) opened the position with **neither SL nor TP** | Opens nothing, returns `None` and logs the error | The stop the caller asked for was silently dropped |
| `volume=True` was traded as 1 lot; NaN or infinite numbers crashed deep inside | Refused (returns `None`). Numeric strings (`"0.1"`) are still converted as in 2.x | A stray bool must not become one lot |
| `sl_type="offset"` with an explicit `price=` was measured from the live quote | Measured from `price`. With instant execution the order fills only within `deviation` of `price`, so this is a few points at most. With market execution the broker ignores `price` and fills at the market, so a stale `price` moves the stops by the same distance. A stop that lands on the wrong side of the market is rejected by the server (10016), not applied | The stops follow the price the caller asked for. Use absolute stops if they must not depend on `price` |
| On retcode 10027 it pressed **Ctrl+E** via `pyautogui` | Logs "enable Algo Trading" and returns the receipt | Ctrl+E *toggles* Algo Trading and is typed into whichever window has focus |
| A partial or only-queued (PLACED) market entry counted as opened | Logged as an error; the receipt is still returned, so check `receipt.retcode` (10009 = done) | The bot believed it held the full size |
| Retcode 10008 (`PLACED`) for limit orders was treated as failure and re-sent | Treated as success | Limit orders could be placed more than once |
| `ticket=` on `OpenPosition`/`Buy`/`Sell`/`BuyLimit`/`SellLimit` was forwarded as `position` | Refused: returns `None`, logs an error | On hedging accounts it turned an entry into a close of that position |
| Comments longer than 31 characters made `order_send` fail with `None` | Rejected before sending, logged | Explicit error instead of a crash downstream |
| Prices rounded to `digits` | Prices snapped to the symbol's tick size | Symbols with tick 0.25 were rejected |
| Fixed filling: FOK for market entries, IOC for closes and limit orders | Filling chosen from the symbol's allowed modes (FOK > IOC > RETURN); limit orders on exchange-execution symbols use RETURN | Brokers without FOK rejected every order (10030); IOC cancelled exchange limits unless instantly fillable |

### Closing and cancelling

| 2.x | 3.0 | Why |
|---|---|---|
| `Close()` looped until every position closed, e.g. through a whole closed-market weekend | One attempt per position (requotes retried up to 3 times); a failure returns `False`. A reversal written as `Close(s); Buy(s, v)` must check that `Close` returned `True`, or it may end up holding both | Same as the endless entry loop |
| `Close()` always returned `False` | `True` if at least one position closed and none failed, else `False` | The return value was meaningless |
| `Close(symbol=None, ticket=...)` crashed | Each position is closed on its own symbol | It priced the close with the `symbol` argument |
| `Close(None)` without a ticket crashed without closing anything | Still closes nothing: logs an error, returns `False` | Forwarding `None` would close every position on the account |
| `Close(ticket=0)` / `GetPositions(ticket=0)` passed 0 to `positions_get` | Refused: `False` / `[]`, error logged | 0 may mean "no filter" and close the whole account |
| A partly filled close counted as closed | Reported as a failure (`PARTIAL_FILL`), `Close()` returns `False` | The rest of the position was left open silently |
| `CancelOrders(None)` | Cancels nothing and logs an error | Guards against a missing symbol acting on the whole account |
| `CancelOrders` could loop forever on a failed cancel | One attempt per order (requotes retried), failures logged | Same as above |

### Returned objects

| 2.x | 3.0 | Why |
|---|---|---|
| Entries returned MT5's raw `OrderSendResult` | A `LegacyReceipt` named tuple with the same fields in the same order: attribute access, indexing and `_asdict()` work. `request` is always `None` | 3.x does not keep the echoed request |
| `GetPositions()` returned raw MT5 `TradePosition` objects | `LegacyPosition` named tuples with every `TradePosition` field in MT5's order; `as_dict=True` returns the same 12 keys as before | No dependency on MT5 internals |
| `broker.password` attribute | Removed; credentials are kept in a non-printing object | The password showed up in debug dumps |

## Star import: MetaTrader5 names stay, three others are gone

`from PythonMetaTrader5 import *` still brings in the `MetaTrader5`
namespace (`symbol_info`, `ORDER_TYPE_BUY`, ...), as in 2.x (ADR 0010). Two
differences:

- `Tick` is now the library's own quote model, not MT5's tick struct. Use
  `MetaTrader5.Tick` if you need the struct.
- `time`, `logger` (loguru) and `pyautogui`, which 2.x also leaked through the
  star import, are gone. Import them yourself:

```python
import time
```

## Logging

2.x printed through `loguru`. 3.0 uses the standard `logging` module (logger
`PythonMetaTrader5`). Errors and warnings still reach stderr without any
configuration; to see info messages:

```python
import logging

logging.basicConfig(level=logging.INFO)
```

## Moving to the 3.0 API

| 2.x | 3.0 |
|---|---|
| `Broker(login, password, server)` | `connect(login, password, server)` → `Ok(trader)` / `Err(error)` |
| `OpenPosition(s, "buy", v, sl=1000, sl_type="offset")` | `trader.open_position(s, "buy", v, sl=Stop.points(1000))` |
| `OpenPosition(s, "buy", v, sl=1.05)` | `trader.open_position(s, "buy", v, sl=1.05)` |
| `Close("EURUSD")` | `trader.close_positions("EURUSD")` |
| `BuyLimit(s, v, stoplimit=1.1)` | `trader.place_limit_order(s, "buy", v, 1.1)` (no automatic market fill when crossed) |
| `CancelOrders(s)` | `trader.cancel_pending_orders(s, kind=PendingKind.LIMIT)` |
| `GetPositions(as_dict=True)` | see below |
| `Disconnect()` | `trader.shutdown()` or `with trader:` |

`positions()` returns a `Result`, and its dictionaries use `side: "buy"` /
`"sell"` instead of the numeric `type`:

```python
match trader.positions():
    case Ok(positions):
        rows = [p.to_dict() for p in positions]
    case Err(error):
        print("cannot list positions:", error)
```
