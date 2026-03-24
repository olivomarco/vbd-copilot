# TODO: Add unit tests for AccountService
#
# This file is intentionally left empty. Use GitHub Copilot to generate
# comprehensive unit tests as part of Challenge 03: Test-Driven Development.
#
# AccountService methods to cover:
#
#   get_account
#     - returns the account when account_id exists
#     - raises AccountNotFoundError when account_id is missing
#
#   create_account
#     - creates and returns an Account with the supplied fields
#     - assigns a unique integer id
#     - raises DuplicateAccountError when account_number is already registered
#
#   update_account
#     - updates owner_name when supplied
#     - leaves unchanged fields intact
#     - raises AccountNotFoundError for an unknown account_id
#     - raises AccountClosedError when the account is inactive
#
#   update_balance
#     - stores the new balance on the account record
#     - raises AccountClosedError when the account is inactive
#
#   close_account
#     - sets is_active to False when balance is zero
#     - raises ValidationError when balance is non-zero
#     - raises AccountClosedError when account is already closed
#
# Hint: use the fixtures in conftest.py as your starting point. Ask Copilot:
#   "Generate pytest unit tests for AccountService covering all methods."
