"""The unit-test fakes must look like the real MetaTrader5 package.

Kept outside tests/unit on purpose: the autouse fixture there replaces the
module with FakeMT5, which would make this a comparison of the fake with
itself. Skipped where the package is not installed (it exists only on
Windows); the Windows CI job runs it against the real wheel.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from PythonMetaTrader5.legacy.views import LegacyPosition, LegacyReceipt
from tests.unit.fake_mt5 import CONSTANTS, FakeMT5, raw_order, raw_position, symbol_info

mt5 = pytest.importorskip("MetaTrader5")


def fields(structseq: Any) -> tuple[str, ...]:
    # The package's result types are C struct sequences without `_fields`; the
    # repr of a filled instance lists the names in order.
    sample = structseq(tuple(range(structseq.n_fields)))
    return tuple(re.findall(r"(\w+)=", repr(sample)))


def test_fake_constants_have_the_real_values() -> None:
    assert {name: getattr(mt5, name) for name in CONSTANTS} == CONSTANTS


def test_legacy_shapes_match_the_real_result_types() -> None:
    assert LegacyPosition._fields == fields(mt5.TradePosition)
    assert LegacyReceipt._fields == fields(mt5.OrderSendResult)


def test_fake_rows_only_use_fields_the_real_objects_have() -> None:
    assert set(vars(raw_position())) == set(fields(mt5.TradePosition))
    assert set(vars(FakeMT5().send_result)) == set(fields(mt5.OrderSendResult)) - {"request"}
    assert set(vars(raw_order())) <= set(fields(mt5.TradeOrder))
    assert set(vars(symbol_info())) <= set(fields(mt5.SymbolInfo))
