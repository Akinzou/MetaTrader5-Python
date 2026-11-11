# API reference

Everything below is importable from the package root:

```python
from PythonMetaTrader5 import connect, Trader, Stop, Ok, Err, ErrorKind
```

Generated from the source and its type hints. The behaviour behind each call,
with examples, is in the [user guide](../guide.md).

| Page | Contents |
|---|---|
| [Connecting and trading](trading.md) | `connect`, `Trader`, `RetryPolicy`, `ANY_MAGIC`, `AnyMagic` |
| [Orders and stops](orders.md) | `Side`, `Stop`, `StopKind`, `PendingKind` |
| [Results and errors](results.md) | `Result`, `Ok`, `Err`, `TradeError`, `ErrorKind`, `BatchFailure` |
| [Account state](market.md) | `Position`, `PendingOrder`, `TradeReceipt`, `Tick` |
| [2.x Broker (deprecated)](legacy.md) | `Broker` |
