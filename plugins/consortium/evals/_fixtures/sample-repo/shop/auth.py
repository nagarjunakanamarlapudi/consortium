"""Authentication fixture."""


def authenticated(user_id: str | None) -> bool:
    return bool(user_id)
