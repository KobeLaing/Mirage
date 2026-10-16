"""Password hashing with Argon2id.

Argon2id is deliberately slow and memory-hungry, so an attacker who steals the
users table can only try a few guesses per second per CPU core instead of
billions. Each hash string carries its own random salt and cost settings, so
two users with the same password still get different hashes, and we can raise
the cost later without breaking existing hashes.

Plaintext passwords only ever exist in memory for the length of one request.
They are never stored and never logged.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


class Passwords:
    def __init__(self, *, fast: bool = False):
        # `fast` is for the test suite only: the same algorithm with tiny cost
        # settings, so hundreds of tests don't each spend 50 ms hashing.
        self._hasher = (
            PasswordHasher(time_cost=1, memory_cost=8 * 1024, parallelism=1) if fast else PasswordHasher()
        )
        # Used when the username doesn't exist (see verify()).
        self._dummy_hash = self._hasher.hash("mirage-timing-equaliser")

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, stored_hash: str | None, password: str) -> bool:
        """True only if `password` matches `stored_hash`.

        When there is no account (stored_hash is None) we still run a full
        Argon2 check against a dummy hash. Without it, "unknown user" would
        answer much faster than "wrong password", and an attacker could time
        the responses to find out which usernames exist.
        """
        try:
            if stored_hash is None:
                self._hasher.verify(self._dummy_hash, password)
                return False
            return self._hasher.verify(stored_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
