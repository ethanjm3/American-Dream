"""Money in milliunits, the integer representation YNAB uses everywhere.

One currency unit is 1000 milliunits ($12.34 is 12340). Holding amounts as
integers keeps month-to-month rollover exact, which floats do not.

``to_currency`` follows the rounding the published ``ynab`` SDK applies
(``convertMilliUnitsToCurrencyAmount``, observed in ynab@4.5.0
``dist/utils.js``): round to the currency's precision with JavaScript
``Math.round`` semantics, i.e. halves round toward +infinity, so -2.5 -> -2.
"""

from __future__ import annotations

import math

MILLI = 1000


def to_milli(amount: float) -> int:
    """Currency amount -> milliunits, rounding half away from zero."""
    scaled = amount * MILLI
    return int(math.copysign(math.floor(abs(scaled) + 0.5), scaled))


def js_round(x: float) -> int:
    """JavaScript ``Math.round``: nearest integer, halves toward +infinity."""
    return math.floor(x + 0.5)


def to_currency(milliunits: int, decimal_digits: int = 2) -> float:
    step = 10 ** (3 - min(3, decimal_digits))
    return round(js_round(milliunits / step) * step / MILLI, decimal_digits)


def fmt(milliunits: int, symbol: str = "$") -> str:
    v = to_currency(milliunits)
    return f"-{symbol}{-v:,.2f}" if v < 0 else f"{symbol}{v:,.2f}"
