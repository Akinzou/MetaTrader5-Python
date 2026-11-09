# ADR 0009: One lock per process around terminal calls

- Status: accepted (3.0.0)

## Context

After a failed `order_send`, the adapter reads `last_error()` to decide
between `TERMINAL_ERROR` (never sent, safe to resend) and `OUTCOME_UNKNOWN`
(may have reached the server). `last_error()` is process-global. In a threaded
webhook server, thread B's call can overwrite the error before thread A reads
it. A's lost order could then be labelled "never sent", and resending it
would open a duplicate position.

## Decision

`adapters/mt5_terminal.py` holds a module-level `threading.RLock`. Every
public adapter method runs under it, so a call and the error read that
explains it are atomic.

We rejected a lock per adapter. `connect()` builds a new adapter each time,
and every adapter in a process talks to the same global MT5 session, so
separate locks would not exclude each other.

## Consequences

- Terminal calls from different threads run one at a time. MT5 serves one
  session per process anyway, so no parallelism is lost.
- A slow call (a login waiting for `timeout_ms`) delays the other threads
  for that long.
- Calls that user code makes to the `MetaTrader5` module directly are outside
  the lock. The README says so.
