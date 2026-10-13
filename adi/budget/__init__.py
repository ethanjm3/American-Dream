"""Zero-based envelope budgeting modelled on YNAB, applied to the index.

``money``      integer milliunit amounts
``targets``    category targets and how much each still needs
``engine``     the ledger and the month-by-month budget computation
``household``  runs an index household through a year of budgeting

See ``docs/ynab-reverse-engineering.md``.
"""
