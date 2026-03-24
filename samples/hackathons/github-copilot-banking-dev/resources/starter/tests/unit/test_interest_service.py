# TODO: Add unit tests for InterestService
#
# This file is intentionally left empty. Use GitHub Copilot to generate
# unit tests as part of Challenge 04: Debugging and Code Quality.
# There are deliberate bugs in interest_service.py - the tests you write
# should expose them.
#
# InterestService methods to cover:
#
#   calculate_simple_interest
#     - standard positive case: verify the formula I = P * r * (days / 365)
#     - zero principal should return 0.0
#     - zero rate should return 0.0
#     - zero days should return 0.0
#     - negative days should raise or return a sentinel (verify current behaviour)
#
#   calculate_compound_interest
#     - standard positive case: verify growth after 12 months at known rate
#     - zero principal should return 0.0
#     - one month at 5% annual on 10000 principal should be approx 40.74
#
#   apply_monthly_interest
#     - delegates to calculate_compound_interest with months=1
#     - returns the interest amount (not the new balance)
#
# Reference calculation for test assertions:
#   Simple interest: 1000 principal, 5% annual rate, 30 days
#     Correct answer: 1000 * 0.05 * 30 / 365 = 4.1095...  (rounds to 4.11)
#     With the bug:   1000 * 0.05 * 31 / 365 = 4.2465...  (rounds to 4.25)
#   The test should assert approximately 4.11, which will FAIL against the
#   buggy implementation. That is the expected outcome for challenge-04.
#
# Hint: ask Copilot:
#   "Write pytest tests for InterestService that expose precision and
#    off-by-one bugs in the interest calculation methods."
