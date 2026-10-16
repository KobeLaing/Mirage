"""Session cookies and CSRF tokens.

How a session works:
1. At login we create a random secret (32 bytes) and store only its SHA-256
   in the sessions table.
2. The cookie value is that secret, signed and timestamped with SESSION_SECRET
   (itsdangerous). A tampered or expired cookie fails the signature check
   before we ever touch the database.
3. On each request we verify the signature, hash the secret, and look the
   session up. Logout marks the row revoked, so the cookie stops working even
   though its signature would still be valid.

CSRF: the session cookie is sent automatically by the browser, so another site
could try to make a signed-in user's browser submit a request. To block that,
every state-changing request must also carry an X-CSRF-Token header. The token
is an HMAC of the session cookie, so only our frontend, which received the
token from the API, can produce it. Another site can neither read our cookie
nor our API responses.
"""

import hashlib
import hmac
import secrets

from itsdangerous import BadSignature, URLSafeTimedSerializer

SESSION_COOKIE = "mirage_session"


def session_id(raw_secret: str) -> str:
    """What the database stores: a one-way hash of the cookie's secret."""
    return hashlib.sha256(raw_secret.encode()).hexdigest()


class SessionTokens:
    def __init__(self, signing_key: str, ttl_seconds: int):
        self.ttl_seconds = ttl_seconds
        self._serializer = URLSafeTimedSerializer(signing_key, salt="mirage.session")
        # A separate key derived from the signing key, so a CSRF token can never
        # be mistaken for (or turned into) a session signature.
        self._csrf_key = hmac.new(signing_key.encode(), b"mirage.csrf", hashlib.sha256).digest()

    @staticmethod
    def new_secret() -> str:
        return secrets.token_urlsafe(32)

    def sign(self, raw_secret: str) -> str:
        return self._serializer.dumps(raw_secret)

    def unsign(self, cookie_value: str) -> str | None:
        """The raw secret, or None if the cookie is forged, malformed or expired."""
        try:
            value = self._serializer.loads(cookie_value, max_age=self.ttl_seconds)
        except BadSignature:  # SignatureExpired is a subclass
            return None
        return value if isinstance(value, str) else None

    def csrf_for(self, cookie_value: str) -> str:
        return hmac.new(self._csrf_key, cookie_value.encode(), hashlib.sha256).hexdigest()

    def csrf_matches(self, cookie_value: str, supplied: str) -> bool:
        # compare_digest takes the same time whether the first or last character
        # differs, so the token can't be guessed one character at a time.
        return hmac.compare_digest(self.csrf_for(cookie_value), supplied)
