# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [3.0.0] - 2026-11-09

Complete rewrite. See [MIGRATION.md](MIGRATION.md) for every behaviour change.

### Added
- `connect()` and the `Trader` API returning `Result` (`Ok` / `Err`) values.
- Typed errors (`TradeError`, `ErrorKind`) and `BatchFailure` for close-all /
  cancel-all with per-ticket outcomes.
- `Stop.points()` / `Stop.at_price()` for SL/TP; plain floats are prices.
- `Stop.parse(value, StopKind)` returns `Ok(stop)` / `Err(INVALID_STOPS)` for
  values that may be bad at runtime; the constructors raise `ValueError`, and
  a `kind` that is not a `StopKind` raises `TypeError`.
- Magic-number support for entries and as a filter for close/cancel/queries.
  `close_positions()` / `cancel_pending_orders()` default to the trader's own
  magic; `ANY_MAGIC` acts on the whole account; a `ticket` is closed whatever
  its magic (ADR 0011). `Broker.Close` / `CancelOrders` keep acting on every
  magic, as in 2.x. `connect(magic=...)` must be an integer from 0 to 2**64-1; a magic-0
  trader logs a warning when a close/cancel affects magic-0 (manual) trades.
- Volume validation against the symbol's min/max/step.
- Filling mode chosen from the symbol's allowed modes.
- Hidden symbols are selected into Market Watch automatically.
- `py.typed`: the package ships type information.
- CI: ruff, mypy --strict, tests on Python 3.10-3.14, a Windows job against the
  real `MetaTrader5` package, Semgrep, a 300-line file limit, build checks.
- Integration tests against a demo account.
- Contract tests comparing the unit-test fakes with the real `MetaTrader5`
  package (run by the Windows CI job).
- Thread safety: every terminal call holds one process-wide lock.

### Changed
- `Broker` is a deprecated facade over `Trader` with the 2.x method names. It
  returns `LegacyPosition` / `LegacyReceipt` named tuples with the fields and
  field order of MT5's `TradePosition` / `OrderSendResult`.
- The `MetaTrader5` namespace is still re-exported for `import *` and attribute
  access, but lazily, and each re-exported call holds the session lock (a
  sequence of calls is not atomic; ADR 0010). `Tick` now means
  the library's quote model, and importing the library no longer imports
  `MetaTrader5`.
- `Position` carries every `TradePosition` field (`swap`, `identifier`, ...);
  `TradeReceipt` gains `retcode_external`.
- Bounded retries (requotes only) instead of endless loops.
- Prices snap to the symbol's tick size instead of rounding to `digits`.
- Logging moved from `loguru` to the standard `logging` module.
- Minimum Python version is 3.10.
- License metadata is CC-BY-NC-4.0 (the MIT classifier was wrong).

### Removed
- `pyautogui` Ctrl+E hotkey on retcode 10027.
- The `import *` re-exports of `time`, loguru's `logger` and `pyautogui`.
- The `Broker.password` attribute.

### Safety
- An empty symbol (`""`) is rejected instead of meaning "every symbol".
- `order_send` failures that may have reached the server are reported as
  `OUTCOME_UNKNOWN`, never as a plain terminal error.
- Market deals (entries and closes) succeed only on DONE: a partial fill is a
  `PARTIAL_FILL` error, a queued (PLACED) one is `OUTCOME_UNKNOWN`; neither is
  re-sent.
- Logins that would be coerced (`True`, `12345678.9`, non-ASCII digits) are
  rejected, in `connect()` and in `Broker`.
- Every failed login shuts the terminal session down, and `Broker` refuses to
  trade until a login succeeds.
- `sl=0` / `tp=0`, stops that resolve to zero or below, tickets that are not
  positive integers, `volume=True` and non-finite numbers are rejected before
  sending.
- Entries on a symbol whose data cannot price an order (no usable tick size
  or point, a NaN tick size, negative digits, volume step 0, ...) return
  `BROKEN_SYMBOL_DATA` instead of sending NaN prices or stops on the entry price.
  Points stops additionally need a usable `point`. NaN or infinite quotes are
  `NO_PRICE`. Closing still works on such symbols.
- `positions(symbol, ticket=...)` applies both filters (MT5 drops the symbol
  once a ticket is given).
- Pending orders on exchange-execution symbols use RETURN filling.
- `Broker.Close(None)` / `Broker.CancelOrders(None)` act on nothing.

### Fixed
- `Close(ticket=...)` with `symbol=None` crashed.
- `CancelOrders` and `Close` could loop forever.
- Limit orders confirmed with `PLACED` (10008) were re-sent.
- `len(None)` crash when the terminal returned no positions.
- Comments of 30 or more UTF-16 units (most emoji count as 2), which the
  `MetaTrader5` package refuses although its docs allow 31, and comments that
  are not `str`, are refused locally as `INVALID_ARGUMENT`.

## [2.3.2]

Last release of the 2.x line.
