import pytest

from PythonMetaTrader5.domain.errors import ErrorKind
from PythonMetaTrader5.domain.symbol import Filling, SymbolSpec
from PythonMetaTrader5.result import Err, Ok


def eurusd(**overrides: object) -> SymbolSpec:
    fields: dict[str, object] = {
        "name": "EURUSD",
        "digits": 5,
        "point": 0.00001,
        "tick_size": 0.00001,
        "volume_min": 0.01,
        "volume_max": 100.0,
        "volume_step": 0.01,
        "filling_flags": 1,
    }
    fields.update(overrides)
    return SymbolSpec(**fields)  # type: ignore[arg-type]


def test_normalize_price_rounds_to_tick_without_float_noise() -> None:
    assert eurusd().normalize_price(1.123456) == 1.12346
    assert eurusd().normalize_price(1.1) == 1.1


def test_normalize_price_uses_tick_size_coarser_than_point() -> None:
    index = eurusd(name="US500", digits=2, point=0.01, tick_size=0.25)
    assert index.normalize_price(5780.13) == 5780.25


def test_normalize_price_falls_back_to_point_when_tick_size_missing() -> None:
    assert eurusd(tick_size=0.0).normalize_price(1.123456) == 1.12346


@pytest.mark.parametrize("volume", [0.01, 0.1, 0.37, 100.0])
def test_valid_volume_is_accepted(volume: float) -> None:
    assert eurusd().validate_volume(volume) == Ok(volume)


@pytest.mark.parametrize("volume", [0.0, 0.005, 0.015, 100.01, -1.0])
def test_invalid_volume_is_rejected(volume: float) -> None:
    result = eurusd().validate_volume(volume)
    assert isinstance(result, Err)
    assert result.error.kind is ErrorKind.INVALID_VOLUME


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        (1, Filling.FOK),
        (2, Filling.IOC),
        (3, Filling.FOK),
        (0, Filling.RETURN),
        (4, Filling.RETURN),
    ],
)
def test_market_filling_prefers_fill_or_kill(flags: int, expected: Filling) -> None:
    assert eurusd(filling_flags=flags).market_filling() is expected
