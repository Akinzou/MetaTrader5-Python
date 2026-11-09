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
- `Stop` enforces the same rule on itself in `__post_init__`: it stores a
  positive finite float, and a points distance drops its sign. It raises
  `ValueError` on 0, bool, NaN, infinities and strings, because such a `Stop`
  cannot exist. Plain floats passed as `sl` / `tp` are checked without raising
  (`stop_input`) and come back as `INVALID_STOPS`. The number rule itself lives
  once, in `domain/amounts.py`. An earlier draft stored the raw value and
  checked it only in `stop_input`. We dropped it because it left `Stop`
  without invariants, `Stop.points(-1000) != Stop.points(1000)`, and every
  other consumer of `Stop` would have needed its own check.
- The price is checked inside `validate_entry`, before the symbol lookup and
  after the side, comment and stops. A bad price never costs a terminal round
  trip, and a bad side is still the first error reported.
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
- `Stop.points(0)` raises `ValueError` when it is built, instead of the server
  rejecting it with 10016.
- On the `Result` paths (`sl` / `tp` floats, volume, prices, `Stop.parse`),
  signalling-NaN Decimals and ints too large for a float are refused without
  raising. `float(Decimal("sNaN"))` and `float(10**400)` both raise, so
  `positive_float` handles both. Large but finite floats (`1e305`) pass that
  rule, but they overflow on the tick grid (`1e305 / 1e-5` is `inf`).
  `SymbolSpec.price_on_grid` is the one place every caller-supplied level is
  put on the grid, and it refuses those as well as levels that snap to 0.
  Quote prices come from the terminal already on the grid. The `Stop`
  constructors raise `ValueError` on any invalid value.
- Broken data from the terminal is the same problem on the other side. A
  point of 0 put a points stop on the entry price, and a point or tick size
  of inf priced orders at NaN. These are the broker's fault, so they come
  back as `TERMINAL_ERROR`, not as `INVALID_*`, which would blame the
  caller. Every entry calls `SymbolSpec.check_tradable()` (tick size, step,
  digits, volume limits), including market orders without stops.
  `points_to_price` also checks `point`, which only points stops need. The
  adapter refuses NaN and infinite quotes as `NO_PRICE`. Closing never runs
  these checks. We rejected an invariant on the whole `SymbolSpec`: it made a
  position on such a symbol impossible to close, although closing needs only
  the filling flags.
