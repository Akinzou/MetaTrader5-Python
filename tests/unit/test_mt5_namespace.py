"""2.x re-exported the MetaTrader5 namespace; scripts call symbol_info() through it."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from PythonMetaTrader5.legacy import mt5_namespace


def test_public_names_are_taken_and_ours_win_a_collision() -> None:
    module = SimpleNamespace(symbol_info=print, ORDER_TYPE_BUY=0, Tick=object, _private=1)
    names = mt5_namespace.public_names(module, taken={"Tick"})  # type: ignore[arg-type]
    assert names == {"symbol_info": print, "ORDER_TYPE_BUY": 0}


def test_nothing_is_re_exported_without_the_package() -> None:
    assert mt5_namespace.public_names(None, taken=set()) == {}


def test_load_gives_none_where_the_package_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "MetaTrader5", None)
    assert mt5_namespace.load() is None
