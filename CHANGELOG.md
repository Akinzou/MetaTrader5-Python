# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [3.0.0] - Unreleased

Complete rewrite. See [MIGRATION.md](MIGRATION.md) for every behaviour change.

### Added
- `connect()` and the `Trader` API returning `Result` (`Ok` / `Err`) values.
- Typed errors (`TradeError`, `ErrorKind`) and `BatchFailure` for close-all /
  cancel-all with per-ticket outcomes.
- `Stop.points()` / `Stop.at_price()` for SL/TP; plain floats are prices.
- Magic-number support for entries and as a filter for close/cancel/queries.
- Volume validation against the symbol's min/max/step.
- Filling mode chosen from the symbol's allowed modes.
- Hidden symbols are selected into Market Watch automatically.
- `py.typed`: the package ships type information.
- CI: ruff, mypy --strict, tests on Python 3.10-3.14, a Windows job against the
  real `MetaTrader5` package, Semgrep, a 300-line file limit, build checks.
- Integration tests against a demo account.

### Changed
- `Broker` is a deprecated facade over `Trader` with the 2.x method names.
- Bounded retries (requotes only) instead of endless loops.
- Prices snap to the symbol's tick size instead of rounding to `digits`.
- Logging moved from `loguru` to the standard `logging` module.
- Minimum Python version is 3.10.
- License metadata is CC-BY-NC-4.0 (the MIT classifier was wrong).

### Removed
- `pyautogui` Ctrl+E hotkey on retcode 10027.
- The `from MetaTrader5 import *` re-export.
- The `Broker.password` attribute.

### Safety
- An empty symbol (`""`) is rejected instead of meaning "every symbol".
- `order_send` failures that may have reached the server are reported as
  `OUTCOME_UNKNOWN`, never as a plain terminal error.
- A partly filled close is a `PARTIAL_FILL` error.
- A failed login shuts the terminal session down.

### Fixed
- `Close(ticket=...)` with `symbol=None` crashed.
- `CancelOrders` and `Close` could loop forever.
- Limit orders confirmed with `PLACED` (10008) were re-sent.
- `len(None)` crash when the terminal returned no positions.

## [2.3.2]

Last release of the 2.x line.
