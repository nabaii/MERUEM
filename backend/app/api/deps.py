import uuid
from typing import Annotated

from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.models.account import Account, Role
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)

DbDep = Annotated[Session, Depends(get_db)]

# Dev bypass: a singleton in-memory account used when no token is supplied.
_DEV_ACCOUNT = Account(
    id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    email="dev@meruem.local",
    full_name="Dev User",
    hashed_password="",
    role=Role.admin,
    is_active=True,
)


def get_current_account(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
    db: DbDep,
) -> Account:
    # Auth bypass — skip login for local development
    return _DEV_ACCOUNT


def require_admin(account: Annotated[Account, Depends(get_current_account)]) -> Account:
    if account.role != Role.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return account


CurrentAccount = Annotated[Account, Depends(get_current_account)]
AdminAccount = Annotated[Account, Depends(require_admin)]
