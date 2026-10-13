"""A clean-room zero-based ("envelope") budget engine modelled on YNAB.

Nothing here is derived from YNAB's code. The rules come from YNAB's public
API contract and support documentation; see
``docs/ynab-reverse-engineering.md`` for each rule, its source, and what is
inferred rather than stated.

State is a ledger: accounts, categories, transactions, and the amount
assigned to each category in each month. Every number the user sees (Ready
to Assign, a category's Available, overspending, credit card payment
balances, Age of Money) is recomputed from that ledger, so editing a
transaction or an assignment in any month is always consistent.

Amounts are integer milliunits (see ``money``). Outflows are negative.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date

from .targets import Target, add_months

READY_TO_ASSIGN = "Inflow: Ready to Assign"
CC_GROUP = "Credit Card Payments"


def month_of(d: date) -> date:
    return date(d.year, d.month, 1)


@dataclass(frozen=True)
class Account:
    name: str
    on_budget: bool = True
    credit: bool = False


@dataclass
class Category:
    name: str
    group: str
    target: Target | None = None
    payment_for: str | None = None   # credit card account this category pays


@dataclass(frozen=True)
class Transaction:
    date: date
    account: str
    amount: int
    category: str | None = None
    transfer_account: str | None = None
    memo: str = ""
    transfer_pair: int | None = field(default=None, compare=False)
    starting_balance: bool = False


@dataclass
class CategoryMonth:
    category: str
    group: str
    assigned: int = 0
    activity: int = 0
    available: int = 0
    cash_overspent: int = 0
    credit_overspent: int = 0
    goal: dict | None = None


@dataclass
class MonthView:
    month: date
    income: int
    assigned: int
    activity: int
    to_be_budgeted: int
    age_of_money: int | None
    categories: dict[str, CategoryMonth]


class Plan:
    def __init__(self, name: str = "Plan"):
        self.name = name
        self.accounts: dict[str, Account] = {}
        self.categories: dict[str, Category] = {}
        self.transactions: list[Transaction] = []
        self.assigned: dict[tuple[date, str], int] = defaultdict(int)
        self._edits = 0
        self._cache: tuple | None = None

    # ---- editing -----------------------------------------------------

    def add_account(self, name: str, *, on_budget: bool = True, credit: bool = False,
                    balance: int = 0, opened: date | None = None) -> Account:
        self._edits += 1
        if name in self.accounts:
            raise ValueError(f"account {name!r} exists")
        if credit and not on_budget:
            raise ValueError("credit cards are on-budget accounts")
        acct = Account(name, on_budget, credit)
        self.accounts[name] = acct
        if credit:
            self.add_category(name, CC_GROUP, payment_for=name)
        if balance:
            if opened is None:
                raise ValueError("an opening balance needs an opening date")
            # YNAB books an on-budget opening balance as income (a credit
            # card's debt instead becomes the payment category's shortfall).
            cat = READY_TO_ASSIGN if on_budget and not credit else None
            self.transactions.append(Transaction(opened, name, balance, cat, memo="Starting Balance",
                                                starting_balance=True))
        return acct

    def add_category(self, name: str, group: str, *, target: Target | None = None,
                     payment_for: str | None = None) -> Category:
        self._edits += 1
        if name in self.categories or name == READY_TO_ASSIGN:
            raise ValueError(f"category {name!r} exists")
        cat = Category(name, group, target, payment_for)
        self.categories[name] = cat
        return cat

    def add_transaction(self, when: date, account: str, amount: int,
                        category: str | None = None, memo: str = "") -> Transaction:
        self._edits += 1
        acct = self._account(account)
        if acct.on_budget and category is None:
            raise ValueError("on-budget transactions need a category")
        if not acct.on_budget and category is not None:
            raise ValueError("tracking-account transactions have no category")
        if category is not None and category != READY_TO_ASSIGN:
            if category not in self.categories:
                raise KeyError(category)
            if self.categories[category].payment_for:
                raise ValueError("pay a card with a transfer, not a categorised transaction")
        if category == READY_TO_ASSIGN and amount < 0:
            raise ValueError("Ready to Assign only takes inflows")
        t = Transaction(when, account, amount, category, memo=memo)
        self.transactions.append(t)
        return t

    def transfer(self, when: date, source: str, dest: str, amount: int,
                 category: str | None = None, memo: str = "") -> None:
        """Move ``amount`` (> 0) from ``source`` to ``dest``.

        Between two on-budget accounts (including paying a credit card)
        money stays in the budget and needs no category. Crossing the
        budget boundary needs one: the on-budget side is categorised.
        """
        self._edits += 1
        if amount <= 0:
            raise ValueError("transfer amount must be positive")
        a, b = self._account(source), self._account(dest)
        crosses = a.on_budget != b.on_budget
        if crosses and category is None:
            raise ValueError("a transfer between budget and tracking accounts needs a category")
        if not crosses and category is not None:
            raise ValueError("a transfer within the budget (or within tracking) takes no category")
        out_cat = category if a.on_budget and crosses else None
        in_cat = category if b.on_budget and crosses else None
        i = len(self.transactions)
        self.transactions.append(Transaction(when, source, -amount, out_cat, dest, memo, i + 1))
        self.transactions.append(Transaction(when, dest, amount, in_cat, source, memo, i))

    def assign(self, month: date, category: str, amount: int) -> None:
        """Set (not add to) the amount assigned to ``category`` in ``month``."""
        self._edits += 1
        if category not in self.categories:
            raise KeyError(category)
        self.assigned[(month_of(month), category)] = amount

    def move(self, month: date, source: str, dest: str, amount: int) -> None:
        m = month_of(month)
        self.assign(m, source, self.assigned[(m, source)] - amount)
        self.assign(m, dest, self.assigned[(m, dest)] + amount)

    def _account(self, name: str) -> Account:
        if name not in self.accounts:
            raise KeyError(f"no account {name!r}")
        return self.accounts[name]

    # ---- computing ---------------------------------------------------

    def months(self, through: date | None = None) -> list[date]:
        stamps = [month_of(t.date) for t in self.transactions] + [m for m, _ in self.assigned]
        if through is not None:
            stamps.append(month_of(through))
        if not stamps:
            return []
        out, m, last = [], min(stamps), max(stamps)
        while m <= last:
            out.append(m)
            m = add_months(m, 1)
        return out

    def compute(self, through: date | None = None) -> dict[date, MonthView]:
        """Every month's view, from the first month with data through ``through``.

        Results are cached until the plan is edited. Treat them as read-only.
        """
        key = (self._edits, through, tuple((n, id(c.target)) for n, c in self.categories.items()))
        if self._cache is None or self._cache[0] != key:
            self._cache = (key, self._compute(through))
        return self._cache[1]

    def _compute(self, through: date | None) -> dict[date, MonthView]:
        months = self.months(through)
        by_month: dict[date, list[Transaction]] = defaultdict(list)
        for t in self.transactions:
            by_month[month_of(t.date)].append(t)

        normal = [c for c in self.categories.values() if not c.payment_for]
        payment = {c.payment_for: c for c in self.categories.values() if c.payment_for}
        carry = {c: 0 for c in self.categories}
        funded_from = {c: 0 for c in self.categories}  # assigned earlier in a NEED period
        tbb, cash_overspent_prev = 0, 0
        views: dict[date, MonthView] = {}

        for m in months:
            txns = by_month[m]
            income = sum(t.amount for t in txns if t.category == READY_TO_ASSIGN)
            rows: dict[str, CategoryMonth] = {}
            cc_moved = defaultdict(int)       # funded card spending -> payment category
            cash_overspent_total = 0

            for c in normal:
                start = carry[c.name]
                assigned = self.assigned.get((m, c.name), 0)
                cash = credit = 0
                credit_by_card: dict[str, int] = defaultdict(int)
                for t in txns:
                    if t.category != c.name or not self.accounts[t.account].on_budget:
                        continue
                    if self.accounts[t.account].credit:
                        credit += t.amount
                        credit_by_card[t.account] += t.amount
                    else:
                        cash += t.amount
                activity = cash + credit
                available = start + assigned + activity
                # Cash is spent first; credit spending is "funded" to the
                # extent money is left in the category for it. Funded
                # spending moves to the card's payment category; refunds on
                # a card move money back out of it.
                room = max(0, start + assigned + cash)
                for card, amt in credit_by_card.items():
                    if amt < 0:
                        covered = min(-amt, room)
                        room -= covered
                        cc_moved[card] += covered
                    else:
                        cc_moved[card] -= amt
                cash_over = credit_over = 0
                if available < 0:
                    credit_spent = -min(0, credit)
                    credit_over = min(-available, credit_spent)
                    cash_over = -available - credit_over
                    cash_overspent_total += cash_over
                row = CategoryMonth(c.name, c.group, assigned, activity, available, cash_over, credit_over)
                if c.target is not None:
                    if c.target.goal_type == "NEED" and c.target.whole_amount and c.target.months_to_budget(m) == c.target.cadence_months:
                        funded_from[c.name] = 0
                    row.goal = c.target.evaluate(m, start, assigned, funded_from[c.name])
                    funded_from[c.name] += assigned
                rows[c.name] = row
                carry[c.name] = max(0, available)

            for card, c in payment.items():
                start = carry[c.name]
                assigned = self.assigned.get((m, c.name), 0)
                payments = sum(t.amount for t in txns
                               if t.account == card and t.transfer_account
                               and self.accounts[t.transfer_account].on_budget)
                activity = cc_moved[card] - payments
                available = start + assigned + activity
                cash_over = -available if available < 0 else 0
                cash_overspent_total += cash_over
                row = CategoryMonth(c.name, c.group, assigned, activity, available, cash_over, 0)
                if c.target is not None:
                    row.goal = c.target.evaluate(m, start, assigned, funded_from[c.name])
                rows[c.name] = row
                carry[c.name] = max(0, available)

            assigned_total = sum(r.assigned for r in rows.values())
            tbb += income - assigned_total - cash_overspent_prev
            cash_overspent_prev = cash_overspent_total
            spent = sum(t.amount for t in txns if t.category not in (None, READY_TO_ASSIGN)
                        and self.accounts[t.account].on_budget)
            views[m] = MonthView(m, income, assigned_total, spent, tbb, None, rows)

        # Money assigned in a later month is no longer available to assign
        # in an earlier one, so a month shows the lowest running balance
        # from it onward, but never less than zero on account of a later
        # month: that shortfall shows in the later month itself. Future
        # income never counts early.
        floor = None
        for m in reversed(months):
            own = views[m].to_be_budgeted
            later = floor
            floor = own if floor is None else min(floor, own)
            if own >= 0 and later is not None:
                views[m].to_be_budgeted = max(0, min(own, later))

        aom = self.age_of_money_by_month()
        for m in months:
            views[m].age_of_money = aom.get(m)
        return views

    def ready_to_assign(self, month: date) -> int:
        return self.compute(month)[month_of(month)].to_be_budgeted

    # ---- age of money ------------------------------------------------

    def age_of_money_by_month(self, window: int = 10, min_outflows: int = 10) -> dict[date, int | None]:
        """Average age, in days, of the money behind the last ``window`` outflows.

        Nothing is reported until ``min_outflows`` outflows have happened.
        Starting balances and transfers within the budget are not inflows.

        Cash entering the budget (inflows to on-budget accounts that are not
        transfers between them) queues up first-in, first-out. Each cash
        outflow leaving the budget spends the oldest dollars; its age is the
        dollar-weighted number of days those dollars waited. Credit card
        spending is not cash leaving until the card is paid, so card
        payments count as outflows and card purchases do not.
        """
        def leaves_budget(t: Transaction) -> bool:
            acct = self.accounts[t.account]
            if not acct.on_budget or t.amount >= 0:
                return False
            if acct.credit:
                return False
            if t.transfer_account is None:
                return True
            dest = self.accounts[t.transfer_account]
            return dest.credit or not dest.on_budget

        def enters_budget(t: Transaction) -> bool:
            acct = self.accounts[t.account]
            if not acct.on_budget or acct.credit or t.amount <= 0 or t.starting_balance:
                return False
            return t.transfer_account is None or not self.accounts[t.transfer_account].on_budget

        queue: deque[list] = deque()   # [date, remaining]
        ages: list[int] = []

        def average() -> int | None:
            if len(ages) < max(1, min_outflows):
                return None
            recent = ages[-window:]
            return round(sum(recent) / len(recent))

        result: dict[date, int | None] = {}
        current = None
        for t in sorted(self.transactions, key=lambda t: (t.date, t.amount < 0)):
            m = month_of(t.date)
            if current is not None and m != current:
                result[current] = average()
            current = m
            if enters_budget(t):
                queue.append([t.date, t.amount])
            elif leaves_budget(t):
                need, weighted, covered = -t.amount, 0, 0
                while need and queue:
                    lot = queue[0]
                    take = min(need, lot[1])
                    weighted += take * (t.date - lot[0]).days
                    covered += take
                    need -= take
                    lot[1] -= take
                    if lot[1] == 0:
                        queue.popleft()
                if covered:
                    ages.append(round(weighted / covered))
        if current is not None:
            result[current] = average()
        # carry the last known value through months without transactions
        last = None
        for m in self.months():
            if m in result:
                last = result[m]
            result[m] = last
        return result

    # ---- assigning ---------------------------------------------------

    def auto_assign_underfunded(self, month: date) -> int:
        """Fund each category's ``goal_under_funded`` in category order.

        Stops when Ready to Assign runs out, leaving later categories short.
        As in YNAB, a balance target with no date (TB) is skipped. YNAB
        orders by overspending, then due date, then category order; here
        category order *is* the priority, so callers order categories.
        Returns the total assigned.
        """
        m = month_of(month)
        total = 0
        for name in list(self.categories):
            view = self.compute(m)[m]
            avail = view.to_be_budgeted
            goal = view.categories[name].goal
            if avail <= 0:
                break
            if not goal or goal["goal_type"] == "TB" or goal["goal_under_funded"] <= 0:
                continue
            amt = min(avail, goal["goal_under_funded"])
            self.assign(m, name, self.assigned.get((m, name), 0) + amt)
            total += amt
        return total
