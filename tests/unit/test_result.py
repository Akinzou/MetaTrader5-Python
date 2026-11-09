from PythonMetaTrader5.result import Err, Ok, Result


def describe(result: Result[int, str]) -> str:
    match result:
        case Ok(value):
            return f"ok:{value}"
        case Err(error):
            return f"err:{error}"


def test_ok_and_err_are_pattern_matchable() -> None:
    assert describe(Ok(3)) == "ok:3"
    assert describe(Err("boom")) == "err:boom"


def test_ok_and_err_report_their_state() -> None:
    assert Ok(1).is_ok()
    assert not Ok(1).is_err()
    assert Err("x").is_err()
    assert not Err("x").is_ok()
