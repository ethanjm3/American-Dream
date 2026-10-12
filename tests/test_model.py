"""Unit tests for the pieces of the model that don't need the network."""

import numpy as np
import pandas as pd
import pytest

from adi import components, data, retirement


def test_mortgage_payment_matches_textbook():
    # $200,000 at 6% for 30 years -> $1,199.10 a month.
    assert components.mortgage_payment(200_000, 6.0, 30) / 12 == pytest.approx(1199.10, abs=0.01)


def test_average_interest_first_year():
    # First-year interest on $200,000 at 6%/30y is about $11,933.
    assert components.average_interest(200_000, 6.0, 30, 1) == pytest.approx(11_933, abs=5)


def test_average_interest_whole_loan_equals_total_interest():
    total = components.mortgage_payment(100_000, 5.0, 30) * 30 - 100_000
    assert components.average_interest(100_000, 5.0, 30, 30) * 30 == pytest.approx(total, rel=1e-9)


def test_splice_backward_and_forward():
    primary = pd.Series([100.0, 110.0], index=[2000, 2001])
    fallback = pd.Series([40.0, 50.0, 55.0, 66.0], index=[1999, 2000, 2001, 2002])
    out = data.splice([primary, fallback])
    assert out[1999] == pytest.approx(80.0)    # 40 * (100/50)
    assert out[2002] == pytest.approx(132.0)   # 66 * (110/55)
    assert out[2000] == 100.0 and out[2001] == 110.0


def test_splice_requires_overlap():
    with pytest.raises(ValueError):
        data.splice([pd.Series([1.0], index=[2000]), pd.Series([1.0], index=[1990])])


@pytest.mark.parametrize("birth,fra", [(1937, 65), (1940, 65.5), (1950, 66), (1957, 66.5), (1960, 67), (1990, 67)])
def test_full_retirement_age(birth, fra):
    assert retirement.full_retirement_age(birth) == pytest.approx(fra)


def test_claim_factors():
    assert retirement.worker_claim_factor(62, 67) == pytest.approx(0.70)
    assert retirement.worker_claim_factor(62, 66) == pytest.approx(0.75)
    assert retirement.worker_claim_factor(62, 65) == pytest.approx(0.80)
    assert retirement.worker_claim_factor(70, 67) == pytest.approx(1.24)
    assert retirement.spouse_claim_factor(62, 67) == pytest.approx(0.325)
    assert retirement.spouse_claim_factor(62, 66) == pytest.approx(0.35)
    assert retirement.spouse_claim_factor(67, 67) == pytest.approx(0.5)


def test_anchor_terms_parse():
    assert list(components._terms("UTILS-PHONE")) == [(1, "UTILS"), (-1, "PHONE")]
    assert list(components._terms("A+B-C")) == [(1, "A"), (1, "B"), (-1, "C")]


def test_loan_cost_factor_zero_rate_limit():
    assert components._loan_cost_factor(np.array([1e-9]))[0] == pytest.approx(0, abs=1e-6)


def test_browser_model_matches_python():
    """The interactive page's JS model reproduces the Python baseline."""
    import json
    import shutil
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    data_file = root / "web" / "adi_data.json"
    if not shutil.which("node") or not data_file.exists():
        pytest.skip("node or web/adi_data.json not available")
    out = subprocess.run(["node", str(root / "tests/js/parity.js"), str(root / "web/template.html"),
                          str(data_file)], capture_output=True, text=True, check=True).stdout
    for line in out.strip().splitlines():
        r = json.loads(line)
        assert r["cost"] < 1e-3 and r["retirement"] < 1e-3, r
