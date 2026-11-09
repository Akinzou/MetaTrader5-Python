"""The one rule for "a positive finite number", shared by Stop and the input checks."""

from __future__ import annotations

import math
from decimal import Decimal
from numbers import Real


def positive_float(value: object, *, unsigned: bool = False) -> float | None:
    """``value`` as a positive finite float, or None when it is not one.

    numbers.Real rather than float, so numpy scalars from pandas-based bots
    pass, plus Decimal (not a Real) for bots that keep money as Decimal. bool
    is excluded because it is a Real (True == 1) and would trade one lot.
    NaN Decimals are refused before float(): float(Decimal("sNaN")) raises.
    ``unsigned`` drops the sign first (a distance), after the NaN check, because
    abs(Decimal("sNaN")) raises too.
    """
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
        return None
    if isinstance(value, Decimal) and value.is_nan():
        return None
    try:
        number = abs(float(value)) if unsigned else float(value)
    except (OverflowError, ValueError):
        return None  # 10**400 and odd Real subclasses: "not a usable number"
    return number if math.isfinite(number) and number > 0 else None
