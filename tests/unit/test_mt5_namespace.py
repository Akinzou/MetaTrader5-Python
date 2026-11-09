"""2.x re-exported the MetaTrader5 namespace; scripts call symbol_info() through it."""

from __future__ import annotations

import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import pytest

import PythonMetaTrader5
from PythonMetaTrader5.adapters import mt5_session
from PythonMetaTrader5.adapters.mt5_terminal import MetaTrader5Terminal
from PythonMetaTrader5.domain.errors import ErrorKind
from PythonMetaTrader5.domain.market import Tick
from PythonMetaTrader5.result import Err

from .fake_mt5 import FakeMT5


def star_import() -> dict[str, Any]:
    namespace: dict[str, Any] = {}
    exec("from PythonMetaTrader5 import *", namespace)  # noqa: S102 - the 2.x idiom itself
    return namespace


def test_the_2x_star_import_brings_mt5_names_and_ours_win(no_real_terminal: FakeMT5) -> None:
    names = star_import()
    assert names["ORDER_TYPE_BUY"] == 0
    assert names["Tick"] is Tick  # MT5 has its own Tick struct; ours wins
    assert names["Broker"] is PythonMetaTrader5.Broker
    names["symbol_select"]("EURUSD", True)
    assert no_real_terminal.calls[-1] == ("symbol_select", ("EURUSD", True), {})
    for leaked_by_2x in ("time", "logger", "pyautogui"):
        assert leaked_by_2x not in names


def test_re_exported_functions_run_under_the_adapters_session_lock(
    no_real_terminal: FakeMT5,
) -> None:
    held: list[bool] = []
    no_real_terminal.last_error = lambda: held.append(mt5_session.SESSION._is_owned()) or (1, "")  # type: ignore[attr-defined, method-assign, func-returns-value]
    PythonMetaTrader5.last_error()
    assert held == [True]


def test_without_the_package_only_our_names_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "MetaTrader5", None)
    names = star_import()
    assert "Broker" in names
    assert "symbol_info" not in names
    with pytest.raises(AttributeError, match="symbol_info"):
        _ = PythonMetaTrader5.symbol_info


@pytest.mark.parametrize(
    "failure",
    [
        ImportError("DLL load failed while importing _core"),
        ModuleNotFoundError("No module named 'numpy'", name="numpy"),
        AttributeError("module 'numpy' has no attribute '_ARRAY_API'"),
        ValueError("numpy.dtype size changed"),
    ],
)
def test_a_broken_install_is_reported_without_breaking_imports_or_tools(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    def broken(name: str) -> None:
        raise failure

    # Replaces the importlib reference inside mt5_session only, not the stdlib.
    monkeypatch.setattr(mt5_session, "importlib", SimpleNamespace(import_module=broken))
    with pytest.warns(RuntimeWarning, match="cannot be imported"):
        names = star_import()
    assert "connect" in names  # a script using only connect() still imports
    assert "symbol_info" not in names
    assert not hasattr(PythonMetaTrader5, "symbol_info")
    with pytest.raises(AttributeError, match="cannot be imported") as raised:
        _ = PythonMetaTrader5.symbol_info
    assert isinstance(raised.value.__cause__, ImportError)
    loaded = MetaTrader5Terminal.load()
    assert isinstance(loaded, Err)
    assert loaded.error.kind is ErrorKind.CONNECTION_FAILED
    assert str(failure) in loaded.error.message


def test_importing_the_library_does_not_import_metatrader5() -> None:
    # The re-export is lazy: pure-domain users and tooling never pay for or
    # depend on the MetaTrader5 import.
    probe = "import sys, PythonMetaTrader5; print('MetaTrader5' in sys.modules)"
    out = subprocess.run(  # noqa: S603 - fixed arguments, our own interpreter
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "False"


def test_dir_lists_our_names_and_the_mt5_names(no_real_terminal: FakeMT5) -> None:
    listed = dir(PythonMetaTrader5)
    assert {"Broker", "connect", "symbol_info", "ORDER_TYPE_BUY"} <= set(listed)
