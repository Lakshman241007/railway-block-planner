"""
FastAPI dependency injection utilities.

Provides database session lifecycle management for request handlers.
"""

from __future__ import annotations

from typing import Generator, Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database.connection import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding an isolated database session per request.
    Ensures proper session closure upon request completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_role(x_user_role: Optional[str] = Header(default="operator", alias="X-User-Role")) -> str:
    """
    Extract the role from the X-User-Role header.
    Defaults to 'operator' for backwards compatibility with unauthenticated or legacy callers.
    """
    if not x_user_role:
        return "operator"
    return x_user_role.strip().lower()


def require_operator_role(role: str = Depends(get_current_role)) -> str:
    """
    FastAPI dependency that enforces Operator-only permissions for mutation operations.
    Rejects requests initiated with role 'employee' with HTTP 403 Forbidden.
    """
    if role == "employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: Employee role is restricted to read-only access.",
        )
    return role

