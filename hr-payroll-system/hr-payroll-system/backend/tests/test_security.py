import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.security import (
    hash_password,
    verify_password,
    validate_password_strength,
    create_access_token,
    get_current_user,
    require_role,
)
from app.errors import BusinessRuleError, ForbiddenError, UnauthorizedError


class PasswordTests(unittest.TestCase):
    def test_hash_and_verify(self):
        h = hash_password("Secret123!")
        self.assertTrue(verify_password("Secret123!", h))
        self.assertFalse(verify_password("wrong", h))

    def test_verify_invalid_hash(self):
        self.assertFalse(verify_password("x", "not-a-hash"))

    def test_strength_ok(self):
        validate_password_strength("ValidPass1!")

    def test_strength_too_short(self):
        with self.assertRaises(BusinessRuleError):
            validate_password_strength("Aa1!")

    def test_strength_no_upper(self):
        with self.assertRaises(BusinessRuleError):
            validate_password_strength("lowercase1!")

    def test_strength_no_lower(self):
        with self.assertRaises(BusinessRuleError):
            validate_password_strength("UPPERCASE1!")

    def test_strength_no_digit(self):
        with self.assertRaises(BusinessRuleError):
            validate_password_strength("NoDigitPass!")

    def test_strength_no_special(self):
        with self.assertRaises(BusinessRuleError):
            validate_password_strength("NoSpecial1")


class JWTTests(unittest.TestCase):
    def test_create_and_decode(self):
        token = create_access_token(42, "Admin", 7)
        user = get_current_user.__wrapped__ if hasattr(get_current_user, "__wrapped__") else None
        import jwt
        from app.config import settings
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        self.assertEqual(payload["sub"], "42")
        self.assertEqual(payload["role"], "Admin")
        self.assertEqual(payload["emp"], 7)


class RBACTests(unittest.TestCase):
    def test_allowed_role(self):
        checker = require_role("Admin", "HR")
        user = {"user_id": 1, "role": "HR", "employee_id": None}
        self.assertEqual(checker(user=user), user)

    def test_denied_role(self):
        checker = require_role("Admin")
        user = {"user_id": 2, "role": "Employee", "employee_id": 5}
        with self.assertRaises(ForbiddenError):
            checker(user=user)


if __name__ == "__main__":
    unittest.main()
