"""Password hashing; compatible with accounts from earlier versions."""

import hashlib
import hmac
import secrets


class PasswordHasher:
    def hash(self, password):
        if not password:
            raise ValueError("Enter a password")
        salt = secrets.token_bytes(16)
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=16384,
            r=8,
            p=1,
            dklen=64,
            maxmem=64 * 1024 * 1024,
        )
        return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"

    def verify(self, password, encoded):
        try:
            algorithm, n, r, p, salt, expected = encoded.split("$")
            if algorithm != "scrypt" or (n, r, p) != ("16384", "8", "1"):
                return False
            digest = hashlib.scrypt(
                password.encode("utf-8"),
                salt=bytes.fromhex(salt),
                n=16384,
                r=8,
                p=1,
                dklen=64,
                maxmem=64 * 1024 * 1024,
            )
            return hmac.compare_digest(digest, bytes.fromhex(expected))
        except (ValueError, TypeError):
            return False
