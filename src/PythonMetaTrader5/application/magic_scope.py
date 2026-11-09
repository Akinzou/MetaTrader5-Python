"""Which magic a close-all / cancel-all acts on when the caller gives none (ADR 0011).

Kept apart from Trader: the rule and the warnings it owes are one decision,
and they would otherwise push trader.py past the file-length limit.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TypeVar

from PythonMetaTrader5.domain.errors import TradeError
from PythonMetaTrader5.domain.inputs import ANY_MAGIC, AnyMagic, magic_filter
from PythonMetaTrader5.result import Ok, Result

log = logging.getLogger("PythonMetaTrader5")
_T = TypeVar("_T")


def resolve(
    own: int, magic: int | AnyMagic | None, ticket: int | None
) -> Result[int | AnyMagic, TradeError]:
    """The magic to filter by: the caller's, else the trader's own."""
    checked = magic_filter(magic)
    if not isinstance(checked, Ok):
        return checked
    if checked.value is not None:
        return Ok(checked.value)
    # A named ticket is explicit intent: filtering it out by magic would
    # report Ok([]) for a position the caller asked to close.
    return Ok(ANY_MAGIC if ticket is not None else own)


def warn_about_default(
    own: int,
    magic: object,
    ticket: int | None,
    matched: list[_T],
    everything: Callable[[], Result[list[_T], TradeError]],
) -> None:
    """Say what the own-magic default cannot know; quiet once a magic is given."""
    if magic is not None or ticket is not None:
        return
    if matched:
        if own == 0:
            # magic 0 stays allowed (it is the connect() default), but then
            # "own" includes every manual trade.
            log.warning(
                "trader magic is 0, which manual trades share: this close/cancel "
                "includes them; set magic at connect(), or pass magic=0 to confirm"
            )
        return
    # Matched nothing: on netting the bot's deal may have merged into a position
    # that kept another magic, and Ok([]) alone would read as "flat". The extra
    # listing runs only on this path.
    others = everything()
    if isinstance(others, Ok) and others.value:
        log.warning(
            "nothing with magic %s to close/cancel; %d item(s) with other magics "
            "left open (on netting a deal merges into a position that keeps its "
            "first magic); pass magic=ANY_MAGIC to include them",
            own,
            len(others.value),
        )
