---
hide:
  - navigation
  - toc
---

# PythonMetaTrader5

A safe, typed trading layer over the official
[`MetaTrader5`](https://pypi.org/project/MetaTrader5/) Python package, built
for bots where a trading call must **never hang, never retry blindly, and
never fail silently**.

[Get started](guide.md#quick-start){ .md-button .md-button--primary }
[API reference](reference/index.md){ .md-button }
[Architecture](architecture.md){ .md-button }

```bash
pip install PythonMetaTrader5
```

<div class="grid cards" markdown>

-   :material-timer-check-outline:{ .lg .middle } **Every call returns**

    ---

    Requotes and missing quotes are retried a bounded number of times with a
    fresh quote. Everything else comes back at once as a typed error.

    [:octicons-arrow-right-24: Retries](guide.md#retries)

-   :material-content-duplicate:{ .lg .middle } **No double fills**

    ---

    Timeouts and lost connections are never retried: the order may already be
    live. They come back as `OUTCOME_UNKNOWN`.

    [:octicons-arrow-right-24: Error kinds](guide.md#error-kinds)

-   :material-shield-check-outline:{ .lg .middle } **No silent defaults**

    ---

    Values MT5 would quietly read as something else, such as `sl=0` or
    `ticket=0`, are refused before anything is sent.

    [:octicons-arrow-right-24: ADR 0008](adr/0008-refuse-values-mt5-misreads.md)

-   :material-code-braces:{ .lg .middle } **Typed results**

    ---

    `Ok(receipt)` or `Err(TradeError)` with an `ErrorKind` instead of magic
    numbers, checked by mypy and your editor.

    [:octicons-arrow-right-24: Results and errors](guide.md#results-and-errors)

-   :material-robot-outline:{ .lg .middle } **Close-all touches only your bot**

    ---

    `close_positions()` and `cancel_pending_orders()` act on the trader's own
    magic number unless told otherwise.

    [:octicons-arrow-right-24: Magic numbers](guide.md#magic-numbers-whose-trades-a-call-touches)

-   :material-sitemap-outline:{ .lg .middle } **Built to be reasoned about**

    ---

    Clean Architecture with ports and adapters, and every non-obvious choice
    recorded as a decision record.

    [:octicons-arrow-right-24: Decisions](adr/index.md)

</div>

## At a glance

--8<-- "README.md:quickstart"

!!! warning "Before trading real money"

    Run your bot on a demo account first, give it its own `magic`, and treat
    `OUTCOME_UNKNOWN` as "maybe filled". The full checklist is in the
    [user guide](guide.md#before-trading-real-money).
