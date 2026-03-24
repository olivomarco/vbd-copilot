from __future__ import annotations

from typing import List

import structlog
from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.models.account import Account, AccountCreate, AccountSummary, AccountUpdate
from app.services.account_service import AccountService

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/", response_model=List[AccountSummary], summary="List accounts")
async def list_accounts(
    active_only: bool = True,
    current_user: dict = Depends(get_current_user),
) -> List[AccountSummary]:
    """Return all accounts visible to the authenticated user."""
    service = AccountService()
    return service.list_accounts(active_only=active_only)


@router.post(
    "/",
    response_model=Account,
    status_code=201,
    summary="Open a new account",
)
async def create_account(
    account_data: AccountCreate,
    current_user: dict = Depends(get_current_user),
) -> Account:
    """Open a new account for a customer.

    Missing: validation that initial_balance is non-negative. A negative opening
    balance is not caught here or in the service layer, which means a caller can
    create an account already in overdraft. Add a Field validator or a service
    check to prevent this.
    """
    service = AccountService()
    return service.create_account(account_data)


@router.get("/{account_id}", response_model=Account, summary="Get account by ID")
async def get_account(
    account_id: int,
    current_user: dict = Depends(get_current_user),
) -> Account:
    service = AccountService()
    return service.get_account(account_id)


@router.patch(
    "/{account_id}",
    response_model=Account,
    summary="Update account details",
)
async def update_account(
    account_id: int,
    account_data: AccountUpdate,
    current_user: dict = Depends(get_current_user),
) -> Account:
    service = AccountService()
    return service.update_account(account_id, account_data)


@router.delete(
    "/{account_id}",
    response_model=Account,
    summary="Close an account",
)
async def close_account(
    account_id: int,
    current_user: dict = Depends(get_current_user),
) -> Account:
    """Close an account. The balance must be zero before closure is allowed."""
    service = AccountService()
    return service.close_account(account_id)
