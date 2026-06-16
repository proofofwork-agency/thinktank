"""Shared identity validation for per-user local storage."""

import re


USER_ID = re.compile(r"^[a-z0-9_-]{1,64}$")


def validate_user_id(user):
    if not USER_ID.fullmatch(user or ""):
        raise ValueError("user id must match ^[a-z0-9_-]{1,64}$")
    return user
