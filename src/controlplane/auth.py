from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from common.settings import Settings

security = HTTPBasic()
credentials_dependency = Depends(security)


def authenticate(settings: Settings):
    def dependency(credentials: HTTPBasicCredentials = credentials_dependency) -> str:
        username_ok = secrets.compare_digest(credentials.username, settings.dashboard_user)
        password_ok = secrets.compare_digest(credentials.password, settings.dashboard_password)
        if not (username_ok and password_ok):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid credentials",
                headers={"WWW-Authenticate": "Basic"},
            )
        return credentials.username

    return dependency
