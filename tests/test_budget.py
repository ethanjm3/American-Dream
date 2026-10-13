"""Tests for the YNAB-style budget engine (adi.budget)."""

from datetime import date

import pytest

from adi.budget import money
from adi.budget.engine import READY_TO_ASSIGN, Plan
from adi.budget.targets import Target

JAN, FEB, MAR = date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 1)
M = money.to_milli


def plan() -> Plan:
    p = Plan()
    p.add_account("Checking")
    p.add_account("Visa", credit=True)
    p.add_category("Groceries", "Food")
    p.add_category("Rent", "Housing")
    return p


# ---- money -------------------------------------------------------------

@pytest.mark.parametrize("milli,digits,expected", [
    (293294, 2, 293.29), (293295, 2, 293.30), (-2500, 0, -2.0),
    (-2501, 0, -3.0), (1234, 3, 1.234), (1235, 1, 1.2),
])
def test_to_currency_matches_sdk_rounding(milli, digits, expected):
    assert money.to_currency(milli, digits) == expected


def test_to_milli_round_trip():
    assert money.to_milli(12.345) == 12345
    assert money.to_milli(-0.0005) == -1
    assert money.fmt(-1234560) == "-$1,234.56"


# ---- ready to assign and rollover --------------------------------------

def test_income_then_assign_reduces_ready_to_assign():
    p = plan()
    p.add_transaction(date(2025, 1, 3), "Checking", M(3000), READY_TO_ASSIGN)
    p.assign(JAN, "Rent", M(1500))
    p.assign(JAN, "Groceries", M(600))
    v = p.compute()[JAN]
    assert v.income == M(3000)
    assert v.to_be_budgeted == M(900)


def test_available_rolls_over():
    p = plan()
    p.add_transaction(date(2025, 1, 3), "Checking", M(1000), READY_TO_ASSIGN)
    p.assign(JAN, "Groceries", M(600))
    p.add_transaction(date(2025, 1, 9), "Checking", M(-450), "Groceries")
    views = p.compute(FEB)
    assert views[JAN].categories["Groceries"].available == M(150)
    assert views[FEB].categories["Groceries"].available == M(150)
    assert views[FEB].to_be_budgeted == M(400)


def test_cash_overspending_comes_out_of_next_months_ready_to_assign():
    p = plan()
    p.add_transaction(date(2025, 1, 3), "Checking", M(1000), READY_TO_ASSIGN)
    p.assign(JAN, "Groceries", M(100))
    p.add_transaction(date(2025, 1, 9), "Checking", M(-130), "Groceries")
    views = p.compute(FEB)
    jan = views[JAN].categories["Groceries"]
    assert (jan.available, jan.cash_overspent, jan.credit_overspent) == (M(-30), M(30), 0)
    assert views[FEB].categories["Groceries"].available == 0
    assert views[FEB].to_be_budgeted == M(870)
    # January cannot hand out money February no longer has.
    assert views[JAN].to_be_budgeted == M(870)


def test_future_assignment_reduces_current_ready_to_assign():
    p = plan()
    p.add_transaction(date(2025, 1, 3), "Checking", M(1000), READY_TO_ASSIGN)
    p.assign(FEB, "Rent", M(700))
    views = p.compute()
    assert views[JAN].to_be_budgeted == M(300)
    assert views[FEB].to_be_budgeted == M(300)


def test_future_income_is_not_available_early():
    p = plan()
    p.add_transaction(date(2025, 2, 3), "Checking", M(1000), READY_TO_ASSIGN)
    views = p.compute(JAN.replace(month=1))
    assert views[FEB].to_be_budgeted == M(1000)
    assert JAN not in views or views[JAN].to_be_budgeted == 0


# ---- credit cards ------------------------------------------------------

def test_funded_card_spending_moves_to_payment_category():
    p = plan()
    p.add_transaction(date(2025, 1, 3), "Checking", M(1000), READY_TO_ASSIGN)
    p.assign(JAN, "Groceries", M(200))
    p.add_transaction(date(2025, 1, 9), "Visa", M(-150), "Groceries")
    v = p.compute()[JAN]
    assert v.categories["Groceries"].available == M(50)
    assert v.categories["Visa"].activity == M(150)
    assert v.categories["Visa"].available == M(150)


def test_credit_overspending_does_not_hit_ready_to_assign():
    p = plan()
    p.add_transaction(date(2025, 1, 3), "Checking", M(1000), READY_TO_ASSIGN)
    p.assign(JAN, "Groceries", M(100))
    p.add_transaction(date(2025, 1, 9), "Visa", M(-160), "Groceries")
    views = p.compute(FEB)
    g = views[JAN].categories["Groceries"]
    assert (g.cash_overspent, g.credit_overspent) == (0, M(60))
    assert views[JAN].categories["Visa"].available == M(100)   # only funded part
    assert views[FEB].to_be_budgeted == M(900)                  # untouched


def test_cash_is_spent_before_credit_in_a_mixed_overspend():
    p = plan()
    p.add_transaction(date(2025, 1, 3), "Checking", M(1000), READY_TO_ASSIGN)
    p.assign(JAN, "Groceries", M(100))
    p.add_transaction(date(2025, 1, 5), "Checking", M(-80), "Groceries")
    p.add_transaction(date(2025, 1, 9), "Visa", M(-50), "Groceries")
    g = p.compute()[JAN].categories["Groceries"]
    assert (g.cash_overspent, g.credit_overspent) == (0, M(30))


def test_card_payment_draws_down_payment_category():
    p = plan()
    p.add_transaction(date(2025, 1, 3), "Checking", M(1000), READY_TO_ASSIGN)
    p.assign(JAN, "Groceries", M(200))
    p.add_transaction(date(2025, 1, 9), "Visa", M(-150), "Groceries")
    p.transfer(date(2025, 1, 20), "Checking", "Visa", M(150))
    v = p.compute()[JAN]
    assert v.categories["Visa"].available == 0
    assert v.to_be_budgeted == M(800)


def test_card_refund_moves_money_back_to_category():
    p = plan()
    p.add_transaction(date(2025, 1, 3), "Checking", M(1000), READY_TO_ASSIGN)
    p.assign(JAN, "Groceries", M(200))
    p.add_transaction(date(2025, 1, 9), "Visa", M(-150), "Groceries")
    p.add_transaction(date(2025, 1, 12), "Visa", M(40), "Groceries")
    v = p.compute()[JAN]
    assert v.categories["Groceries"].available == M(90)
    assert v.categories["Visa"].available == M(110)


# ---- transfers ---------------------------------------------------------

def test_transfer_rules():
    p = plan()
    p.add_account("Savings")
    p.add_account("Brokerage", on_budget=False)
    p.add_category("Investing", "Savings")
    with pytest.raises(ValueError):
        p.transfer(date(2025, 1, 5), "Checking", "Brokerage", M(100))
    with pytest.raises(ValueError):
        p.transfer(date(2025, 1, 5), "Checking", "Savings", M(100), category="Investing")
    p.add_transaction(date(2025, 1, 3), "Checking", M(1000), READY_TO_ASSIGN)
    p.assign(JAN, "Investing", M(300))
    p.transfer(date(2025, 1, 5), "Checking", "Savings", M(500))
    p.transfer(date(2025, 1, 6), "Checking", "Brokerage", M(300), category="Investing")
    v = p.compute()[JAN]
    assert v.categories["Investing"].available == 0
    assert v.to_be_budgeted == M(700)


# ---- targets -----------------------------------------------------------

def test_monthly_funding_target():
    t = Target("MF", M(200))
    assert t.evaluate(JAN, start=M(500), assigned=M(50))["goal_under_funded"] == M(150)


def test_target_balance_counts_carryover():
    t = Target("TB", M(1000))
    g = t.evaluate(JAN, start=M(700), assigned=M(100))
    assert g["goal_under_funded"] == M(200)
    assert g["goal_overall_left"] == M(200)
    assert g["goal_percentage_complete"] == 80


def test_target_by_date_spreads_remaining_amount():
    t = Target("TBD", M(1200), target_date=date(2025, 6, 1))
    g = t.evaluate(JAN, start=0, assigned=0)
    assert g["goal_months_to_budget"] == 6
    assert g["goal_under_funded"] == M(200)
    g = t.evaluate(MAR, start=M(600), assigned=0)
    assert g["goal_under_funded"] == M(150)


def test_need_refill_versus_set_aside():
    refill = Target("NEED", M(600), whole_amount=False)
    aside = Target("NEED", M(600), whole_amount=True)
    assert refill.evaluate(FEB, start=M(250), assigned=0)["goal_under_funded"] == M(350)
    assert aside.evaluate(FEB, start=M(250), assigned=0)["goal_under_funded"] == M(600)


def test_auto_assign_funds_in_order_until_money_runs_out():
    p = plan()
    p.categories["Rent"].target = Target("MF", M(700))
    p.categories["Groceries"].target = Target("MF", M(500))
    # put Rent first
    p.categories = {k: p.categories[k] for k in ("Rent", "Groceries", "Visa")}
    p.add_transaction(date(2025, 1, 3), "Checking", M(1000), READY_TO_ASSIGN)
    assert p.auto_assign_underfunded(JAN) == M(1000)
    v = p.compute()[JAN]
    assert v.categories["Rent"].goal["goal_under_funded"] == 0
    assert v.categories["Groceries"].goal["goal_under_funded"] == M(200)
    assert v.to_be_budgeted == 0


# ---- age of money ------------------------------------------------------

def test_age_of_money_is_fifo():
    p = plan()
    p.add_transaction(date(2025, 1, 1), "Checking", M(100), READY_TO_ASSIGN)
    p.add_transaction(date(2025, 1, 11), "Checking", M(100), READY_TO_ASSIGN)
    p.assign(JAN, "Groceries", M(200))
    # spends the Jan-1 dollars (30 days old) then half Jan-1 / half Jan-11
    p.add_transaction(date(2025, 1, 31), "Checking", M(-50), "Groceries")
    p.add_transaction(date(2025, 1, 31), "Checking", M(-100), "Groceries")
    # second outflow: 50 dollars aged 30 days + 50 aged 20 days -> 25
    assert p.age_of_money_by_month(min_outflows=1)[JAN] == round((30 + 25) / 2)
    assert p.compute()[JAN].age_of_money is None   # YNAB needs ten outflows


def test_card_purchases_do_not_age_money_until_paid():
    p = plan()
    p.add_transaction(date(2025, 1, 1), "Checking", M(100), READY_TO_ASSIGN)
    p.assign(JAN, "Groceries", M(100))
    p.add_transaction(date(2025, 1, 5), "Visa", M(-100), "Groceries")
    assert p.age_of_money_by_month(min_outflows=1)[JAN] is None
    p.transfer(date(2025, 1, 21), "Checking", "Visa", M(100))
    assert p.age_of_money_by_month(min_outflows=1)[JAN] == 20


def test_starting_balance_is_not_an_age_of_money_inflow():
    p = Plan()
    p.add_account("Checking", balance=M(500), opened=date(2024, 12, 1))
    p.add_category("Rent", "Housing")
    p.add_transaction(date(2025, 1, 1), "Checking", M(100), READY_TO_ASSIGN)
    p.add_transaction(date(2025, 1, 21), "Checking", M(-100), "Rent")
    assert p.age_of_money_by_month(min_outflows=1)[JAN] == 20


def test_future_shortfall_shows_in_the_future_month_only():
    p = plan()
    p.add_transaction(date(2025, 1, 3), "Checking", M(500), READY_TO_ASSIGN)
    p.assign(JAN, "Rent", M(500))
    p.assign(FEB, "Rent", M(200))
    views = p.compute()
    assert views[JAN].to_be_budgeted == 0
    assert views[FEB].to_be_budgeted == M(-200)


def test_auto_assign_skips_undated_balance_targets():
    p = plan()
    p.categories["Rent"].target = Target("TB", M(700))
    p.add_transaction(date(2025, 1, 3), "Checking", M(1000), READY_TO_ASSIGN)
    assert p.auto_assign_underfunded(JAN) == 0


# ---- American Dream household ------------------------------------------

@pytest.fixture(scope="module")
def summary_2025():
    import pandas as pd
    s = pd.read_csv("data/processed/summary.csv")
    return s[s.year == 2025].set_index("scenario")


def test_take_home_at_required_income_matches_index_spending(summary_2025):
    from adi.budget import household
    r = summary_2025.loc["A"]
    assert household.take_home(r.cost_pretax, 2025, "A") == pytest.approx(r.spending_after_tax, rel=2e-3)


@pytest.mark.parametrize("scenario", ["A", "B"])
def test_required_income_funds_the_whole_lifestyle(summary_2025, scenario, tmp_path):
    from adi.budget import household
    out = household.run(2025, scenario, summary_2025.loc[scenario].cost_pretax, out_dir=tmp_path)
    cats = out["categories"]
    assert cats["shortfall"].sum() / cats["annual_cost"].sum() < 0.005
    assert cats["cash_overspent"].sum() == 0
    assert (out["months"]["ready_to_assign"] >= 0).all()


def test_median_income_pays_bills_and_cuts_goals(tmp_path):
    from adi.budget import household
    out = household.run(2025, "A", out_dir=tmp_path)
    cats = out["categories"].set_index("category")
    bills = cats[cats.kind.isin(["bill", "annual"])]
    assert (bills.funded_share == 1).all()
    assert cats.loc["Retirement saving", "funded_share"] < 0.5
    assert 0.5 < 1 - cats.shortfall.sum() / cats.annual_cost.sum() < 0.9
    assert (tmp_path / "budget_2025_A_categories.csv").exists()
