# PythonMetaTrader5  [![PyPI Publish](https://github.com/Akinzou/MetaTrader5-Python/actions/workflows/python-publish.yml/badge.svg)](https://github.com/Akinzou/MetaTrader5-Python/actions/workflows/python-publish.yml)  ![PyPI](https://img.shields.io/pypi/v/pythonmetatrader5)  ![Python](https://img.shields.io/badge/python-3.6%2B-blue?logo=python&logoColor=white)  ![License](https://img.shields.io/badge/license-CC_BY--NC_4.0-lightgrey.svg)  [![PyPI Downloads](https://static.pepy.tech/badge/pythonmetatrader5)](https://pepy.tech/projects/pythonmetatrader5)

[![Discord](https://img.shields.io/badge/Join_us_on-Discord-5865F2?logo=discord&logoColor=white&style=for-the-badge)](https://discord.gg/BARYa55KS8)


# MetaTrader5 Python Broker Helper

Minimal, production‑ready helper around the official **MetaTrader5** Python package,
with a single market-entry function and clean handling of **SL/TP as absolute prices or offsets in POINTS**.
Includes utilities to read positions, close them, and manage pending orders.

> Works with: `MetaTrader5`, `loguru`, `pyautogui`

---

## Features

- ✅ One function to open market positions: `OpenPosition(...)`
- ✅ SL/TP can be passed **as absolute prices** or **offsets in POINTS**
- ✅ Automatic price normalization to instrument `digits`
- ✅ Consistent error handling (common MT5 retcodes mapped to messages)
- ✅ Backward‑compat wrappers: `Buy`, `Sell`, `BuySL`, `SellSL`
- ✅ Position helpers: `GetPositions`, `GetPosition`, `GetPositionsBySymbol`
- ✅ Closing and pending orders helpers: `Close`, `SellLimit`, `BuyLimit`, `CancelOrders`

---

## Installation

```bash
pip install MetaTrader5
```

> Ensure your MetaTrader 5 terminal is running, logged in, and **Algo Trading** is enabled.

---

## Quick Start

```python
from PythonMetaTrader5 import Broker
import time

# Login to your account
broker = Broker(96540048, "PASSWORD", "MetaQuotes-Demo")
time.sleep(1)  # small grace period after login

# Open BUY with SL/TP given as OFFSETS IN POINTS
r = broker.OpenPosition(
    "EURUSD", "buy", 0.10,
    sl=1000, sl_type="offset",   # 1000 points (≈ 100 pips on 5-digit symbol)
    tp=1500, tp_type="offset"
)

# Read positions for a symbol
xau_positions = broker.GetPositionsBySymbol("XAUUSD", as_dict=True)

# Close all positions on a symbol
broker.Close("EURUSD")

# Cancel pending limit orders on a symbol
broker.CancelOrders("EURUSD")

# Graceful shutdown
broker.Disconnect()
```

---

## SL/TP Semantics (Important)

- `sl_type` / `tp_type`:
  - `"absolute"` → you pass **absolute prices** (e.g., `1.23456`)
  - `"offset"`   → you pass **offsets in POINTS** (converted using `symbol_info(symbol).point`)

- Offsets are applied from the **current tick price** (`ask` for BUY, `bid` for SELL):
  - BUY : `SL = ask - |sl|*point`, `TP = ask + |tp|*point`
  - SELL: `SL = bid + |sl|*point`, `TP = bid - |tp|*point`

- All calculated prices (including absolute inputs) are normalized to the instrument `digits`.

> If you get `Wrong SL (10016)`, check `symbol_info(symbol).stops_level` and multiply by `point` to know the minimal allowed distance.

---

## API Reference

### `class Broker`

#### `__init__(self, log, password, server)`
Initialize MT5, attempt login, and print account info on success.

- **log**: login number (int or str)
- **password**: account password (str)
- **server**: broker server name (str)

#### `login(self, ToEffect=False) -> bool`
Retrying login loop. If `ToEffect` is `False`, returns immediately on failure.

---

### Market Entry

#### `OpenPosition(self, symbol, side, volume, *, sl=None, tp=None, price=None, comment=None, ticket=None, sl_type="absolute", tp_type="absolute")`
Open a market position.

- **symbol**: e.g., `"EURUSD"`
- **side**: `"buy" | "sell" | "long" | "short"`
- **volume**: lot size (float)
- **sl**/**tp**: number (see `sl_type`/`tp_type`)
- **sl_type**/**tp_type**: `"absolute"` (prices) or `"offset"` (**POINTS**)
- **price**: optional direct price; if `None`, uses current tick (ask/bid) and retries on transient errors
- **comment**: optional MT5 order comment
- **ticket**: existing position id if needed (rarely used for market entry)

**Returns**: result of `order_send` (MT5 `TradeResult`)

**Examples**:
```python
# Absolute prices
broker.OpenPosition("XAUUSD", "sell", 0.10, sl=2400.0, tp=2380.0, sl_type="absolute", tp_type="absolute")

# Offsets in POINTS
broker.OpenPosition("EURUSD", "buy", 0.10, sl=1000, tp=1500, sl_type="offset", tp_type="offset")
```

---

### Backward‑Compat Wrappers

#### `Buy(self, symbol, volume, price=None, *, comment=None, ticket=None)`
Market BUY via `OpenPosition`.

#### `Sell(self, symbol, volume, price=None, *, comment=None, ticket=None)`
Market SELL via `OpenPosition`.

#### `BuySL(self, symbol, volume, sl, price=None, *, comment=None, ticket=None, sl_type="absolute")`
BUY with SL specified (absolute or offset in points).

#### `SellSL(self, symbol, volume, sl, price=None, *, comment=None, ticket=None, sl_type="absolute")`
SELL with SL specified (absolute or offset in points).

---

### Close & Pending Orders

#### `Close(self, symbol, *, comment=None, ticket=None) -> bool`
Iteratively closes all positions for a **ticket** or for a **symbol** (same filtering semantics as `positions_get`). Returns `False` if nothing to close.

#### `SellLimit(self, symbol, volume, stoplimit, price=None, comment=None, ticket=None)`
Create a SELL LIMIT order at `stoplimit`. If current `bid >= stoplimit`, executes a market SELL immediately for consistency.

#### `BuyLimit(self, symbol, volume, stoplimit, price=None, comment=None, ticket=None)`
Create a BUY LIMIT order at `stoplimit`. If current `ask <= stoplimit`, executes a market BUY immediately.

#### `CancelOrders(self, symbol)`
Cancel all BUY/SELL LIMIT pending orders on the given symbol.

#### `Disconnect(self)`
Shutdown MT5 connection.

---

### Positions Helpers

#### `GetPositionsBySymbol(self, symbol: str, as_dict: bool = False) -> list`
Return all open positions for a symbol. If `as_dict=True`, returns a list of plain dictionaries (ready for JSON/GUI).

#### `GetPositions(self, symbol=None, *, ticket=None, as_dict: bool = False) -> list`
Return positions with the same filter style as `Close()`:
- `ticket` provided → that single position
- else `symbol` provided → all for that symbol
- else → all positions

#### `GetPosition(self, symbol=None, *, ticket=None, as_dict: bool = False)`
Return the first matching position (or `None`). Useful when at most one position is expected.

**Example**:
```python
p = broker.GetPosition(symbol="XAUUSD", as_dict=True)
if p:
    print("Ticket:", p["ticket"], "Type:", "BUY" if p["type"] == 0 else "SELL", "Profit:", p["profit"])
```

---

## Error Handling & Retcodes

- Known retcodes are mapped in `RetCodes`:
  - `10027`: Enable Algo Trading in MetaTrader5 app
  - `10018`: Market closed
  - `10016`: Wrong SL

- For `10027`, a `Ctrl+E` hotkey is issued via `pyautogui` to toggle Algo Trading.
- For `10016`, retries are **not** attempted (invalid SL/TP).

---

## Advanced Examples

```python
# 1) BUY with SL absolute price, TP as offset in points
broker.OpenPosition(
    "US500", "buy", 1.0,
    sl=5780.0, sl_type="absolute",
    tp=200,    tp_type="offset"
)

# 2) SELL with both offsets in points
broker.OpenPosition(
    "EURUSD", "sell", 0.2,
    sl=800, tp=1200,
    sl_type="offset", tp_type="offset"
)

# 3) Get all positions as dicts and filter by profit
pos = broker.GetPositions(as_dict=True)
winners = [p for p in pos if p["profit"] > 0]

# 4) Close by ticket
p = broker.GetPosition(symbol="XAUUSD")
if p:
    broker.Close("XAUUSD", ticket=p.ticket)

# 5) Pending orders
broker.BuyLimit("EURUSD", 0.10, stoplimit=1.10000)
broker.SellLimit("EURUSD", 0.10, stoplimit=1.12000)
broker.CancelOrders("EURUSD")
```

---

## Notes

- Ensure the symbol is visible/active in MT5 Market Watch.
- Check `stops_level`/`freeze_level` on your broker if SL/TP are rejected:
  ```python
  info = symbol_info("EURUSD")
  print(info.point, info.digits, info.stops_level, info.freeze_level, info.volume_min, info.volume_step)
  ```
- `volume` must respect broker `volume_min`/`volume_step`.

---

## License

CC-BY-NC 4.0



