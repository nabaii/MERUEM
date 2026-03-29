import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentAccount, DbDep
from app.core.security import (
    create_access_token,
    generate_api_key,
    hash_password,
    verify_password,
)
from app.db.models.account import Account
from app.schemas.auth import AccountOut, ApiKeyResponse, LoginRequest, RegisterRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbDep):
    if db.query(Account).filter(Account.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    account = Account(
        id=uuid.uuid4(),
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbDep):
    account = db.query(Account).filter(Account.email == payload.email).first()
    if not account or not verify_password(payload.password, account.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    if not account.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    token = create_access_token(subject=str(account.id), role=account.role.value)
    return TokenResponse(access_token=token)


@router.post("/api-key", response_model=ApiKeyResponse)
def generate_key(account: CurrentAccount, db: DbDep):
    """Generate (or rotate) an API key for the authenticated account."""
    key = generate_api_key()
    account.api_key = key
    db.add(account)
    db.commit()
    return ApiKeyResponse(api_key=key)


@router.get("/me", response_model=AccountOut)
def me(account: CurrentAccount):
    return account
