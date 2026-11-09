# Architecture

Clean Architecture with Ports & Adapters. Dependencies point inwards only:

```
legacy/ (Broker facade) ─┐
connection.py (connect) ─┼─► application/ ─► domain/ ─► result.py
adapters/ ───────────────┘        ▲
   (implement the ports) ─────────┘
```

| Layer | Package | Knows about | I/O |
|---|---|---|---|
| Domain | `domain/` | trading rules only: sides, stops, symbol specs, retcode meaning, requests, read models | none |
| Application | `application/` | use cases (`Trader`), retry loop, batch reporting, **ports** | only through ports |
| Adapters | `adapters/` | the `MetaTrader5` package, `time.sleep` | yes |
| Composition | `connection.py` | wires adapters into a `Trader` | through adapters |
| Compatibility | `legacy/` | the 2.x `Broker` API mapped onto `Trader` | through `Trader` and ports |

## Ports

There are exactly two, one per process boundary
([ADR 0001](adr/0001-ports-only-at-process-boundaries.md)):

- `Terminal`: the MetaTrader 5 terminal (IPC to `terminal64.exe`).
- `Clock`: waiting between retries.

Pure logic (price normalisation, stop resolution, retcode classification,
volume checks) is plain functions and methods on domain objects, not ports.

## Request flow: `open_position`

1. Validate side, comment, symbol spec and volume. Errors return before any
   order is sent.
2. Build the request from the **current** quote (`Tick.entry_price`), resolving
   `Stop.points` against that price.
3. `execute()` sends it and classifies the retcode
   ([ADR 0003](adr/0003-bounded-retries.md)): success → `Ok`; retryable →
   sleep and rebuild with a fresh quote; anything else → `Err` with the receipt.

## Errors

Expected failures travel as `Result` values
([ADR 0002](adr/0002-result-at-boundaries.md)). Exceptions are reserved for
programming errors (e.g. `RetryPolicy(attempts=0)`).

## Testing

- `tests/unit`: fakes for both ports (`fakes.py`) and for the `MetaTrader5`
  module (`fake_mt5.py`); runs on any OS.
- `tests/integration`: a real terminal on a demo account, opt-in via `MT5_*`.
- CI also builds the adapter against the real `MetaTrader5` wheel on Windows.
