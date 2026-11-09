# Migrating from 2.x to 3.0

3.0 is a rewrite. Existing code using `Broker` keeps running, but the behaviours
below changed on purpose because they were unsafe. Read this list before
upgrading a bot that trades real money.

## Requirements

- Python **3.10+** (2.x claimed 3.6+).
- `pyautogui` and `loguru` are no longer dependencies.

## Behaviour changes in `Broker`

| 2.x | 3.0 | Why |
|---|---|---|
| `OpenPosition`, `BuyLimit`, `SellLimit` retried **forever** on any unknown retcode (e.g. no money, invalid volume, market closed over the weekend), sending an order every 0.5 s | Requotes retried at most 3 times; every other failure returns at once (the receipt is returned, the error is logged) | A weekend webhook would block the bot until Monday; a rejected order was re-sent indefinitely |
| On retcode 10027 it pressed **Ctrl+E** via `pyautogui` | Logs "enable Algo Trading" and returns the receipt | Ctrl+E *toggles* Algo Trading and is typed into whichever window has focus |
| `Close()` always returned `False` | `True` if at least one position closed and none failed, else `False` | The return value was meaningless |
| `Close(symbol=None, ticket=...)` crashed | Each position is closed on its own symbol | It priced the close with the `symbol` argument |
| `CancelOrders` could loop forever on a failed cancel | One attempt per order (requotes retried), failures logged | Same as above |
| Comments longer than 31 characters made `order_send` fail with `None` | Rejected before sending, logged | Explicit error instead of a crash downstream |
| `ticket=` on `OpenPosition`/`Buy`/`Sell`/`BuyLimit`/`SellLimit` was forwarded as `position` | Refused: returns `None`, logs an error | On hedging accounts it turned an entry into a close of that position |
| Retcode 10008 (`PLACED`) for limit orders was treated as failure and re-sent | Treated as success | Limit orders could be placed more than once |
| Prices rounded to `digits` | Prices snapped to the symbol's tick size | Symbols with tick 0.25 were rejected |
| Fixed FOK (open) / IOC (close) filling | Filling chosen from the symbol's allowed modes (FOK > IOC > RETURN) | Brokers without FOK rejected every order (10030) |
| `broker.password` attribute | Removed; credentials are kept in a non-printing object | The password showed up in debug dumps |
| `GetPositions()` returned raw MT5 objects | Returns `LegacyPosition` named tuples with the same fields (`ticket`, `type`, `sl`, ...) | Same attribute access; no dependency on MT5 internals |

## Removed: `from MetaTrader5 import *` re-export

2.x re-exported the whole `MetaTrader5` namespace, so
`from PythonMetaTrader5 import *` also gave you `symbol_info`, `ORDER_TYPE_BUY`
and friends. Import those from the official package instead:

```python
import MetaTrader5 as mt5
info = mt5.symbol_info("EURUSD")
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
| `GetPositions(as_dict=True)` | `[p.to_dict() for p in trader.positions().value]` |
| `Disconnect()` | `trader.shutdown()` or `with trader:` |
