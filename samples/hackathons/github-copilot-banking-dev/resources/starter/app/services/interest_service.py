from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


class InterestService:
    """Calculates simple and compound interest for FinCore Bank accounts.

    Used by the monthly batch process and the /accounts/{id}/interest preview
    endpoint (not yet implemented).

    Known issues logged in backlog:
    - No unit tests exist for this class. Add them before the next release.
    """

    def calculate_simple_interest(
        self,
        principal: float,  # BUG 1: should be Decimal - float loses precision on large balances
        annual_rate: float,
        days: int,
    ) -> float:
        """Return the simple interest earned over a given number of days.

        Formula: I = P * r * t
        where t = days / 365
        """
        try:
            # BUG 2: off-by-one error. The formula uses (days + 1) which adds a full
            # day of interest that should not be there. The correct expression is
            # principal * annual_rate * days / 365.0
            interest = principal * annual_rate * (days + 1) / 365.0
            logger.debug(
                "simple_interest_calculated",
                principal=principal,
                rate=annual_rate,
                days=days,
                interest=interest,
            )
            return interest
        except:  # BUG 3: bare except catches everything including KeyboardInterrupt.
            # ValueError, TypeError, and ZeroDivisionError are all silently swallowed.
            # Callers receive 0.0 and have no way to detect that the calculation failed.
            return 0.0

    def calculate_compound_interest(
        self,
        principal: float,  # BUG 1: should be Decimal
        annual_rate: float,
        months: int,
        compounds_per_year: int = 12,
    ) -> float:
        """Return the compound interest earned over a given number of months.

        Formula: I = P * (1 + r/n)^(n * t) - P
        where t = months / 12, n = compounds_per_year
        """
        try:
            years = months / 12.0
            # BUG 1 (continued): float exponentiation accumulates rounding error
            # on long compounding periods (e.g. 360 months / 30 years)
            amount = principal * (1 + annual_rate / compounds_per_year) ** (
                compounds_per_year * years
            )
            interest = amount - principal
            logger.debug(
                "compound_interest_calculated",
                principal=principal,
                rate=annual_rate,
                months=months,
                interest=interest,
            )
            return interest
        except:  # BUG 3 (repeated): same silent failure pattern
            return 0.0

    def apply_monthly_interest(
        self, account_id: int, balance: float, annual_rate: float
    ) -> float:
        """Calculate one month of compound interest for a given account balance.

        Returns the interest amount to credit; does not update the account directly.
        """
        # Delegates to calculate_compound_interest with periods=1.
        # Inherits Bug 1 and Bug 3 from that method.
        interest = self.calculate_compound_interest(
            principal=balance,
            annual_rate=annual_rate,
            months=1,
            compounds_per_year=12,
        )
        logger.info(
            "monthly_interest_calculated",
            account_id=account_id,
            balance=balance,
            rate=annual_rate,
            interest=interest,
        )
        return interest
