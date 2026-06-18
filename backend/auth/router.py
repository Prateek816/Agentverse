from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from .database import get_db
from .dependencies import get_current_active_user
from .hashing import hash_password, verify_password
from .JWT import create_access_token, create_refresh_token, decode_token
from .models import User
from .schemas import (
    AccessTokenResponse,
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Register ─────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    # Uniqueness checks
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken.",
        )
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered.",
        )

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive access + refresh tokens",
)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = db.query(User).filter(User.username == payload.username).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive.",
        )

    return {
        "access_token": create_access_token(user.username),
        "refresh_token": create_refresh_token(user.username),
        "token_type": "bearer",
    }


# ── Refresh ───────────────────────────────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Get a new access token using a refresh token",
)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token_data = decode_token(payload.refresh_token)
        if token_data.get("type") != "refresh":
            raise credentials_exception
        username: str | None = token_data.get("sub")
        if not username:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise credentials_exception

    return {
        "access_token": create_access_token(user.username),
        "token_type": "bearer",
    }


# ── Me ────────────────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the currently authenticated user's profile",
)
def me(current_user: User = Depends(get_current_active_user)) -> User:
    return current_user


# ── Change password ───────────────────────────────────────────────────────────

@router.put(
    "/me/password",
    response_model=MessageResponse,
    summary="Change the current user's password",
)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    current_user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return {"message": "Password updated successfully."}


# ── Deactivate account ────────────────────────────────────────────────────────

@router.delete(
    "/me",
    response_model=MessageResponse,
    summary="Deactivate the current user's account",
)
def deactivate_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    current_user.is_active = False
    db.commit()
    return {"message": "Account deactivated."}