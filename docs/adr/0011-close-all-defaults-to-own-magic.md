# ADR 0011: Close-all and cancel-all default to the trader's own magic

- Status: accepted (3.0.0). Decided by the package owner on 2026-11-09.

## Context

`close_positions()` and `cancel_pending_orders()` without a `magic` acted on
the whole account, manual trades and other bots included. The README warned
about it in bold, but a bot that forgets `magic` once closes everything. MT5
gives trades opened by hand magic 0.

## Decision

- **Own by default.** Without `magic`, both calls act only on items whose
  magic equals the trader's (`connect(..., magic=...)`). With a `symbol`
  too: `close_positions("EURUSD")` closing someone's manual EURUSD trade is
  the same hazard. This goes beyond the owner's question, which named only
  the no-argument call.
- **The whole account is spelled `ANY_MAGIC`.** An explicit `magic=None` is
  still "own". We chose a named value instead of `None` because a `None` read
  from a missing config key would otherwise widen the call to the whole
  account, the exact accident this change removes.
- **A `ticket` is closed whatever its magic.** The caller named the position.
  Filtering it out would return `Ok([])` with the position still open. An
  explicit `magic` still applies to a ticket.
- **Reads are unchanged.** `positions()` and `pending_orders()` still list
  everything by default; they also accept `ANY_MAGIC`. A read cannot close
  anything, and narrowing it would hide positions from a status screen.
- **A magic outside MT5's ulong is refused** as `INVALID_ARGUMENT` (`"42"`,
  `True`, `1.5`, `-1`, `2**64`). `"42"` would match
  nothing and report an empty success with every position still open.
- **The trader's own magic must be an integer from 0 to 2\*\*64-1** (MT5's
  ulong). `connect()` returns `Err(INVALID_ARGUMENT)` and `Trader(...)`
  raises `ValueError` for `None`, `ANY_MAGIC`, `"1001"` or `True`. Without this check,
  `connect(magic=cfg.get("magic"))` with the key missing made "own" mean
  "every magic" (found in review).
- **`Broker` keeps 2.x.** `Close(symbol)` and `CancelOrders(symbol)` closed
  every magic in 2.x, so the facade passes `ANY_MAGIC`.

## Consequences

- A trader connected with the default `magic=0` shares that magic with manual
  trades, so its close-all still closes them. The protection only works once
  a bot sets its own `magic`. Making `magic` required in `connect()` was
  offered before release; the owner chose to keep `magic=0` as the default
  (2026-11-09). Residual risk: a bot that never sets `magic` still closes
  manual positions and cancels manual pending orders. A defaulted
  close/cancel on a magic-0 trader that matches something logs a warning
  that manual trades are included; an explicit `magic=0` acknowledges it and
  logs nothing.
- On a **netting** account one position per symbol collects every deal, and
  it keeps the magic of the deal that opened it. A bot's deal that merges
  into a manual position is then not "own", and a manual deal that merges
  into the bot's position is. The magic filter cannot separate them; this is
  a property of netting, not of this default. So that `Ok([])` never reads
  as "flat" in silence, a defaulted close/cancel that matches nothing while
  items with other magics are in scope logs a warning naming how many were
  left open (one extra listing, only on that path). If that listing fails,
  the warning says so instead of dropping the error; the close/cancel stays
  `Ok`, because it did what was asked and an `Err` would invite a retry of an
  action that already ran. We did not detect the
  account's margin mode: it would add a port call for a case the warning
  already surfaces.
- `application/magic_scope.py` holds the rule and its warnings, apart from
  `Trader`.
- `close_positions()` ported from 2.x `Close()` now leaves positions of other
  magics open. MIGRATION.md maps `Close(s)` to
  `close_positions(s, magic=ANY_MAGIC)` for an exact equivalent.
- The read/write asymmetry (`None` = all for reads, own for closes) is
  deliberate. The parameter docstrings state it.
