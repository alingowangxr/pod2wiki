"""Simple authentication helpers for pod2wiki web console."""

import hashlib
import secrets
from typing import Optional
from fastapi import Request, HTTPException, status
from pod2wiki.persistence.state import RunStateManager

def hash_password(password: str) -> str:
    """Hash a password using SHA-256 with a simple salt."""
    # Note: In a production environment, use passlib with bcrypt/argon2.
    # For a local console tool, this is a reasonable lightweight compromise.
    salt = "pod2wiki_local_salt"
    return hashlib.sha256((password + salt).encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

async def get_current_user(request: Request, state_mgr: RunStateManager):
    """Dependency to get current logged in user from cookie."""
    username = request.cookies.get("pod2wiki_session")
    if not username:
        # Check if any users exist. If not, allow access to /init-admin
        users = state_mgr.list_users()
        if not users:
            return None
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Cookie"},
        )
    
    user = state_mgr.get_user(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user
