"""Applying one trade action to many positions/orders and reporting per item."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from typing import Protocol, TypeVar

from PythonMetaTrader5.domain.errors import TradeError
from PythonMetaTrader5.domain.market import TradeReceipt
from PythonMetaTrader5.result import Err, Ok, Result


class _Ticketed(Protocol):
    @property
    def ticket(self) -> int: ...

    @property
    def magic(self) -> int: ...


_T = TypeVar("_T", bound=_Ticketed)


@dataclass(frozen=True, slots=True)
class BatchFailure:
    """Some items of a batch (close all / cancel all) failed; others may have succeeded."""

    succeeded: tuple[TradeReceipt, ...]
    errors: tuple[TradeError, ...]

    def __str__(self) -> str:
        return f"{len(self.errors)} failed, {len(self.succeeded)} succeeded: " + "; ".join(
            str(e) for e in self.errors
        )


def run_batch(
    items: Iterable[_T], action: Callable[[_T], Result[TradeReceipt, TradeError]]
) -> Result[list[TradeReceipt], BatchFailure]:
    # Every item is attempted even after a failure: stopping at the first error
    # would leave the remaining positions open while reporting only one problem.
    succeeded: list[TradeReceipt] = []
    errors: list[TradeError] = []
    for item in items:
        match action(item):
            case Ok(receipt):
                succeeded.append(receipt)
            case Err(error):
                errors.append(replace(error, ticket=item.ticket))
    if errors:
        return Err(BatchFailure(tuple(succeeded), tuple(errors)))
    return Ok(succeeded)


def with_magic(items: list[_T], magic: int | None) -> list[_T]:
    return items if magic is None else [item for item in items if item.magic == magic]
