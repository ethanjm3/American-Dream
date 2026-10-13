"""Category targets ("goals") and how much each still needs this month.

Goal types and field meanings come from YNAB's public API contract
(``Category.goal_type`` and the ``goal_*`` fields of the v1 OpenAPI spec):

TB    Target Category Balance: hold ``target`` in the category.
TBD   Target Category Balance by Date: reach ``target`` by ``target_date``,
      spreading what is left evenly over the remaining months.
MF    Monthly Funding: assign ``target`` every month.
NEED  Plan Your Spending: ``target`` is needed each period. ``whole_amount``
      True means "Set aside another" (assign the full target every period);
      False means "Refill up to" (top the category up to the target).
      With ``cadence_months`` > 1 and a ``target_date`` the need is spread
      over the months until the next due date, like TBD.
DEBT  Debt payment: assign ``target`` every month (modelled like MF).

Where a target spreads over several months the monthly need is rounded up
to the next milliunit; YNAB does not document its rounding.

``underfunded`` matches ``goal_under_funded``: the funding still needed in
*this* month to stay on track. ``overall_left`` matches ``goal_overall_left``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

GOAL_TYPES = ("TB", "TBD", "MF", "NEED", "DEBT")


def months_between(start: date, end: date) -> int:
    """Whole calendar months from ``start``'s month to ``end``'s month."""
    return (end.year - start.year) * 12 + end.month - start.month


def add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


@dataclass(frozen=True)
class Target:
    goal_type: str
    target: int                       # milliunits
    target_date: date | None = None   # TBD, or the first due date of a NEED
    whole_amount: bool = False        # NEED only: True = "set aside", False = "refill"
    cadence_months: int = 1           # NEED only: due every n months

    def __post_init__(self):
        if self.goal_type not in GOAL_TYPES:
            raise ValueError(f"unknown goal type {self.goal_type!r}")
        if self.goal_type == "TBD" and self.target_date is None:
            raise ValueError("TBD targets need a target_date")
        if self.cadence_months < 1:
            raise ValueError("cadence_months must be >= 1")

    def months_to_budget(self, month: date) -> int:
        """``goal_months_to_budget``: months left in the period, this one included."""
        due = self.next_due(month)
        return 1 if due is None else max(1, months_between(month, due) + 1)

    def next_due(self, month: date) -> date | None:
        if self.target_date is None:
            return None
        due = date(self.target_date.year, self.target_date.month, 1)
        if self.goal_type == "NEED":
            while due < month:
                due = add_months(due, self.cadence_months)
        return due

    def evaluate(self, month: date, start: int, assigned: int, period_funded: int = 0) -> dict:
        """Funding status for ``month``.

        start          available carried in from last month (>= 0)
        assigned       assigned so far this month
        period_funded  for multi-month NEED/TBD periods: assigned in earlier
                       months of the current period (refill uses the balance
                       instead)
        """
        t, g = self.target, self.goal_type
        if g in ("MF", "DEBT"):
            need_this_month, funded, left = t, assigned, t - assigned
        elif g == "TB":
            need_this_month, funded = t - start, start + assigned
            left = t - funded
        elif g == "TBD":
            left_at_start = t - start
            n = self.months_to_budget(month)
            need_this_month = -(-max(0, left_at_start) // n) if month <= self.target_date else 0
            funded, left = start + assigned, t - start - assigned
        else:  # NEED
            n = self.months_to_budget(month)
            # Set aside counts only what was assigned this period; refill
            # counts what is already in the category.
            base = period_funded if self.whole_amount else start
            left_at_start = t - base
            need_this_month = -(-max(0, left_at_start) // n)
            funded = base + assigned
            left = t - funded
        need_this_month = max(0, need_this_month)
        return {
            "goal_type": g,
            "goal_target": t,
            "goal_months_to_budget": self.months_to_budget(month),
            "goal_under_funded": max(0, need_this_month - assigned),
            "goal_overall_funded": funded,
            "goal_overall_left": max(0, left),
            "goal_percentage_complete": min(100, int(100 * funded / t)) if t > 0 else 100,
        }
