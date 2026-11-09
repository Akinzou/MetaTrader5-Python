# ADR 0008: Refuse input that MT5 would quietly read as something else

- Status: accepted (3.0.0)

## Context

Webhook payloads are loosely typed JSON. Several values that a missing or
malformed field produces have a valid but unintended meaning in MT5:

- `sl=0` / `tp=0` is "no stop", so the position opens unprotected and the call
  reports success.
- `ticket=0` may be read as "no filter" by `positions_get`, which in a close
  would close the whole account.
- `volume=True` is the number 1, so it trades one lot.
- NaN and infinities crashed with `ValueError` / `OverflowError` deep inside
  price rounding, which broke the "every boundary returns a `Result`" rule.

The empty symbol `""` was already refused for the same reason.

## Decision

Refuse these values at the application boundary, before any terminal call:

- Volume and prices must be positive finite real numbers. Bools are excluded.
  `numbers.Real` is used rather than `float`, so numpy scalars from
  pandas-based bots still pass. `Decimal`, which is not a `Real`, is accepted
  explicitly.
- `Stop.at_price()` and `Stop.points()` store their argument unconverted. If
  they called `float()`, `True` would become `1.0` before the check could see
  it.
- The legacy `BuyLimit` / `SellLimit` check the level before comparing it
  with the quote. Otherwise a level of 0 would "cross" the market and be sent
  as a market order.
- A stop is `None` (no stop), a positive finite price or a `Stop`. A stop that
  resolves to zero or below after tick-grid rounding is refused too.
- A ticket is `None` or a positive integer.

The rules live in `domain/inputs.py` as plain functions, not a port, because
they do no I/O. The legacy `Broker` converts numeric strings with `float()`
first, as 2.x did. It does not convert bools, so `True` is refused there as
well.

## Consequences

- 2.x scripts that passed `sl=0` to mean "no stop" now get `None` and an
  error log instead of a trade. MIGRATION.md says so, and `None` is the way
  to ask for no stop.
- An honest zero-distance stop (`Stop.points(0)`) is refused before sending
  instead of being rejected by the server with 10016.
