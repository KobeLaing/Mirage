from typing import Annotated

from pydantic import Field

from app.schemas.common import StrictModel
from app.schemas.users import Profile

USERNAME_PATTERN = r"^[A-Za-z0-9_.-]+$"


class LoginIn(StrictModel):
    username: Annotated[str, Field(min_length=1, max_length=32, pattern=USERNAME_PATTERN)]
    # Upper bound stops someone making us hash a megabyte-long "password".
    password: Annotated[str, Field(min_length=1, max_length=256)]
    # HONEYPOT: the login form's hidden "website" field. People never see it, so
    # it must arrive empty; the check itself is in auth_service.login().
    website: Annotated[str, Field(max_length=500)] = ""


class SessionOut(StrictModel):
    user: Profile
    blind_mode: bool
    # The frontend sends this back as X-CSRF-Token on every POST/PUT/DELETE.
    csrf_token: str
