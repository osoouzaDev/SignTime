from __future__ import annotations

import unittest

from auth.security import (
    hash_password,
    new_token,
    token_hash,
    token_matches,
    validate_password,
    verify_password,
)


class AuthSecurityTests(unittest.TestCase):
    def test_password_is_argon2id_and_can_be_verified(self) -> None:
        password_hash = hash_password("uma-senha-segura-123")
        self.assertTrue(password_hash.startswith("$argon2id$"))
        self.assertTrue(verify_password(password_hash, "uma-senha-segura-123"))
        self.assertFalse(verify_password(password_hash, "senha-incorreta"))

    def test_short_password_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_password("curta")

    def test_session_tokens_are_random_and_stored_as_hash(self) -> None:
        first = new_token()
        second = new_token()
        self.assertNotEqual(first, second)
        self.assertEqual(len(token_hash(first)), 64)
        self.assertTrue(token_matches(token_hash(first), first))
        self.assertFalse(token_matches(token_hash(first), second))


if __name__ == "__main__":
    unittest.main()
