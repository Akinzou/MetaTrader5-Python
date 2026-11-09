# ADR 0003: Bounded retries, never on an unknown outcome

- Status: accepted (3.0.0)

## Context

2.x retried every unknown retcode forever, 0.5 s apart. A bot that hit
NO_MONEY or MARKET_CLOSED blocked indefinitely and kept sending orders.

## Decision

Retry only the codes where the server provably did not execute the request:
REQUOTE (10004), PRICE_CHANGED (10020), PRICE_OFF (10021) and
TOO_MANY_REQUESTS (10024). The default is 3 attempts, 0.5 s apart. Each attempt
rebuilds the request from a fresh quote. An explicit `price` is sent only once.

TIMEOUT (10012) and CONNECTION (10031) come back as `OUTCOME_UNKNOWN` and are
never retried. We chose "report it and let the caller check positions" over
"retry" because a retry after a request that did reach the server opens a
second position without any error.

## Consequences

- Every call returns within `attempts × (delay + round trip)`.
- Callers that handle `OUTCOME_UNKNOWN` must reconcile with `positions()`.
