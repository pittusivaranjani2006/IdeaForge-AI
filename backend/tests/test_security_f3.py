import asyncio
import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from pydantic import ValidationError

from app import main as main_module
from app.api.routes import auth as auth_routes
from app.core import dependencies
from app.core import security
from app.core.config import Settings
from app.schemas.auth import LoginRequest, RegisterRequest

VALID_SECRET = "f3-test-secret-" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6"
VALID_PRODUCTION_ORIGINS = "https://example.com,https://admin.example.com"
FAKE_DATABASE_URL = "postgresql://f3-test-user@db.invalid:5432/ideaforge_fake"
FAKE_DB_CREDENTIAL = "fake-db-user-M9n8B7v6"
FAKE_API_KEY_CREDENTIAL = "fake-api-key-C5d4E3f2"
FAKE_ORIGIN_CREDENTIAL = "fake-origin-user-B1n2M3n4"
FAKE_SECRET_CREDENTIAL = "fake-secret"


def _settings(**kwargs):
    kwargs.setdefault("_env_file", None)
    kwargs.setdefault("database_url", FAKE_DATABASE_URL)
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("ALLOWED_ORIGINS", None)
        os.environ.pop("DATABASE_URL", None)
        return Settings(**kwargs)


def _settings_without_database_url(**kwargs):
    kwargs.setdefault("_env_file", None)
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("DATABASE_URL", None)
        return Settings(**kwargs)


def _prod_settings(**kwargs):
    kwargs.setdefault("_env_file", None)
    kwargs.setdefault("secret_key", VALID_SECRET)
    kwargs.setdefault("app_env", "production")
    kwargs.setdefault("allowed_origins", VALID_PRODUCTION_ORIGINS)
    kwargs.setdefault("database_url", FAKE_DATABASE_URL)
    return Settings(**kwargs)


def _credentials(token="token"):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


class FakeDB:
    def __init__(self, user=None):
        self.user = user
        self.requested_id = None

    def get(self, model, user_id):
        self.requested_id = user_id
        return self.user


class FakeQuery:
    def __init__(self, user):
        self.user = user

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.user


class FakeAuthDB:
    def __init__(self, user=None):
        self.user = user

    def query(self, model):
        return FakeQuery(self.user)

    def commit(self):
        return None


class SettingsValidationTests(unittest.TestCase):
    def test_secret_key_rejects_empty_placeholder_short_and_low_entropy(self):
        for secret in ["", " ", "short", "CHANGE_THIS_IN_PRODUCTION", "a" * 40]:
            with self.subTest(secret=secret[:12]):
                with self.assertRaises(ValidationError):
                    _settings(secret_key=secret)

        valid = _settings(secret_key=VALID_SECRET)
        self.assertEqual(valid.secret_key, VALID_SECRET)

    def test_algorithm_allowlist(self):
        with self.assertRaises(ValidationError):
            _settings(secret_key=VALID_SECRET, algorithm="none")
        with self.assertRaises(ValidationError):
            _settings(secret_key=VALID_SECRET, algorithm="RS256")

        valid = _settings(secret_key=VALID_SECRET, algorithm="hs384")
        self.assertEqual(valid.algorithm, "HS384")

    def test_expiration_bounds(self):
        for minutes in [0, -1, 1441]:
            with self.subTest(minutes=minutes):
                with self.assertRaises(ValidationError):
                    _settings(secret_key=VALID_SECRET, access_token_expire_minutes=minutes)

        valid = _settings(secret_key=VALID_SECRET, access_token_expire_minutes=1440)
        self.assertEqual(valid.access_token_expire_minutes, 1440)

    def test_environment_properties(self):
        settings = _prod_settings()
        self.assertEqual(settings.app_env, "production")
        self.assertTrue(settings.is_production)
        self.assertFalse(settings.is_development)


class ProductionConfigurationTests(unittest.TestCase):
    def test_app_env_normalizes_aliases_and_canonical_values(self):
        cases = [
            ("dev", "development"),
            ("DEV", "development"),
            (" prod ", "production"),
            ("Production", "production"),
            ("test", "test"),
            ("STAGING", "staging"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                settings = _prod_settings(app_env=raw)
                self.assertEqual(settings.app_env, expected)

    def test_app_env_rejects_unsupported_values(self):
        for value in ["", "qa", "local", "prod-production"]:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    _prod_settings(app_env=value)

    def test_development_defaults_and_docs_are_preserved(self):
        settings = _settings(secret_key=VALID_SECRET)
        self.assertEqual(settings.app_env, "development")
        self.assertTrue(settings.is_development)
        self.assertFalse(settings.is_production)
        self.assertEqual(settings.database_url, FAKE_DATABASE_URL)
        self.assertTrue(any("localhost" in origin for origin in settings.cors_origins))
        self.assertTrue(any("127.0.0.1" in origin for origin in settings.cors_origins))
        self.assertEqual(settings.docs_url, "/docs")
        self.assertEqual(settings.redoc_url, "/redoc")

    def test_development_preserves_localhost_cors(self):
        settings = _settings(
            secret_key=VALID_SECRET,
            allowed_origins="http://localhost:5500,http://127.0.0.1:5500",
        )
        self.assertEqual(
            settings.cors_origins,
            ["http://localhost:5500", "http://127.0.0.1:5500"],
        )

    def test_production_disables_docs_and_redoc(self):
        settings = _prod_settings()
        self.assertIsNone(settings.docs_url)
        self.assertIsNone(settings.redoc_url)

    def test_production_requires_explicit_allowed_origins(self):
        with self.assertRaises(ValidationError):
            _settings(
                secret_key=VALID_SECRET,
                app_env="production",
                database_url=FAKE_DATABASE_URL,
            )

    def test_production_rejects_localhost_and_loopback_origins(self):
        origins = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "https://localhost:3000",
            "https://app.localhost",
            "https://127.0.0.2:3000",
            "https://[::1]:3000",
            "https://[::ffff:127.0.0.1]:3000",
        ]
        for origin in origins:
            with self.subTest(origin=origin):
                with self.assertRaises(ValidationError):
                    _prod_settings(allowed_origins=origin)

    def test_production_rejects_http_and_unsupported_schemes(self):
        for origin in [
            "http://example.com",
            "ws://example.com",
            "ftp://example.com",
            "javascript:alert(1)",
        ]:
            with self.subTest(origin=origin):
                with self.assertRaises(ValidationError):
                    _prod_settings(allowed_origins=origin)

    def test_production_rejects_credentials_in_origins(self):
        origins = [
            "https://user@example.com",
            "https://user:pass@example.com",
            "https://@example.com",
            f"https://{FAKE_ORIGIN_CREDENTIAL}@example.com",
        ]
        for origin in origins:
            with self.subTest(origin=origin):
                with self.assertRaises(ValidationError):
                    _prod_settings(allowed_origins=origin)

    def test_production_rejects_paths_queries_fragments_and_params(self):
        origins = [
            "https://example.com/",
            "https://example.com/path",
            "https://example.com?redirect=1",
            "https://example.com#section",
            "https://example.com;param",
        ]
        for origin in origins:
            with self.subTest(origin=origin):
                with self.assertRaises(ValidationError):
                    _prod_settings(allowed_origins=origin)

    def test_production_rejects_wildcard_and_relative_origins(self):
        for origin in ["*", "https://*", "example.com", "/relative"]:
            with self.subTest(origin=origin):
                with self.assertRaises(ValidationError):
                    _prod_settings(allowed_origins=origin)

    def test_production_rejects_malformed_origins(self):
        origins = [
            "",
            " ",
            "https://",
            "https://exa mple.com",
            "https://example.com:bad",
            "https://example.com:70000",
            "https://example.com:0",
            "https://-example.com",
            "https://example..com",
            "https://exa_mple.com",
        ]
        for origin in origins:
            with self.subTest(origin=origin):
                with self.assertRaises(ValidationError):
                    _prod_settings(allowed_origins=origin)

    def test_production_accepts_https_origins_with_valid_ports(self):
        settings = _prod_settings(allowed_origins="https://example.com:443")
        self.assertEqual(settings.cors_origins, ["https://example.com:443"])

    def test_production_accepts_explicit_non_localhost_origins(self):
        settings = _prod_settings()
        self.assertEqual(
            settings.cors_origins,
            ["https://example.com", "https://admin.example.com"],
        )

    def test_production_requires_explicit_database_url(self):
        with self.assertRaises(ValidationError):
            _settings_without_database_url(
                secret_key=VALID_SECRET,
                app_env="production",
                allowed_origins=VALID_PRODUCTION_ORIGINS,
            )

    def test_production_rejects_empty_database_url(self):
        with self.assertRaises(ValidationError):
            _prod_settings(database_url="")

    def test_production_validation_errors_do_not_expose_database_credentials(self):
        marker = "SENSITIVE-DB-CREDENTIAL-MARKER"
        database_url = f"postgresql://{marker}@db.internal:5432/ideaforge"
        with self.assertRaises(ValidationError) as raised:
            _prod_settings(database_url=database_url, access_token_expire_minutes=0)
        self.assertNotIn(marker, str(raised.exception))

    def test_production_secret_validation_still_enforced(self):
        for secret in ["", "short", "CHANGE_THIS_IN_PRODUCTION"]:
            with self.subTest(secret=secret[:12]):
                with self.assertRaises(ValidationError):
                    _prod_settings(secret_key=secret)


class CredentialRedactionTests(unittest.TestCase):
    def test_origin_credentials_are_redacted_in_rendered_validation_errors(self):
        origin = f"https://{FAKE_ORIGIN_CREDENTIAL}@example.com"
        with self.assertRaises(ValidationError) as raised:
            _prod_settings(allowed_origins=origin)
        self.assertNotIn(FAKE_ORIGIN_CREDENTIAL, str(raised.exception))

    def test_database_and_secret_credentials_are_redacted_in_rendered_errors(self):
        database_url = f"postgresql://{FAKE_DB_CREDENTIAL}@db.internal:5432/ideaforge"
        with self.assertRaises(ValidationError) as raised:
            _prod_settings(
                secret_key=FAKE_SECRET_CREDENTIAL,
                database_url=database_url,
            )
        rendered = str(raised.exception)
        self.assertNotIn(FAKE_DB_CREDENTIAL, rendered)
        self.assertNotIn(FAKE_SECRET_CREDENTIAL, rendered)

    def test_startup_logs_do_not_expose_fake_credentials(self):
        origin = f"https://{FAKE_ORIGIN_CREDENTIAL}@example.com"
        database_url = f"postgresql://{FAKE_DB_CREDENTIAL}@db.internal:5432/ideaforge"
        with patch.object(main_module.settings, "openai_api_key", FAKE_API_KEY_CREDENTIAL):
            with patch.object(main_module.settings, "database_url", database_url):
                with patch.object(main_module.settings, "allowed_origins", origin):
                    with self.assertLogs("ideaforge", level="INFO") as captured:
                        asyncio.run(main_module.on_startup())
        rendered = "\n".join(captured.output)
        for marker in [
            FAKE_API_KEY_CREDENTIAL,
            FAKE_DB_CREDENTIAL,
            FAKE_ORIGIN_CREDENTIAL,
        ]:
            self.assertNotIn(marker, rendered)
        self.assertTrue(any("starting up" in line for line in captured.output))


class SecurityHelpersTests(unittest.TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(
            secret_key=VALID_SECRET,
            algorithm="HS256",
            access_token_expire_minutes=60,
        )
        settings_patch = patch.object(security, "settings", self.settings)
        settings_patch.start()
        self.addCleanup(settings_patch.stop)

    def _decode_unrestricted(self, token):
        return jwt.decode(
            token,
            VALID_SECRET,
            algorithms=["HS256"],
            options={"require_exp": True, "require_iat": True, "require_sub": True},
        )

    def test_create_access_token_sets_sub_iat_exp(self):
        token = security.create_access_token("42")
        payload = self._decode_unrestricted(token)
        self.assertEqual(payload["sub"], "42")
        self.assertIsInstance(payload["exp"], int)
        self.assertIsInstance(payload["iat"], int)
        self.assertGreater(payload["exp"], payload["iat"])

    def test_create_access_token_rejects_reserved_extra_claims(self):
        for claim in ["sub", "exp", "iat", "nbf"]:
            with self.subTest(claim=claim):
                with self.assertRaises(ValueError):
                    security.create_access_token("1", extra_claims={claim: "value"})

        token = security.create_access_token("1", extra_claims={"scope": "read"})
        self.assertEqual(self._decode_unrestricted(token)["scope"], "read")

    def test_decode_requires_exp_iat_sub(self):
        now = int(time.time())
        payloads = [
            {"sub": "1", "iat": now},
            {"sub": "1", "exp": now + 300},
            {"iat": now, "exp": now + 300},
        ]
        for payload in payloads:
            with self.subTest(payload_keys=sorted(payload)):
                token = jwt.encode(payload, VALID_SECRET, algorithm="HS256")
                self.assertIsNone(security.decode_access_token(token))

    def test_expired_token_rejected(self):
        now = int(time.time())
        token = jwt.encode(
            {"sub": "1", "iat": now - 120, "exp": now - 60},
            VALID_SECRET,
            algorithm="HS256",
        )
        self.assertIsNone(security.decode_access_token(token))

    def test_wrong_signature_and_wrong_algorithm_rejected(self):
        now = int(time.time())
        payload = {"sub": "1", "iat": now, "exp": now + 300}
        wrong_secret = jwt.encode(
            payload, "another-" + VALID_SECRET, algorithm="HS256"
        )
        wrong_algorithm = jwt.encode(payload, VALID_SECRET, algorithm="HS512")
        self.assertIsNone(security.decode_access_token(wrong_secret))
        self.assertIsNone(security.decode_access_token(wrong_algorithm))

    def test_invalid_sub_types_rejected(self):
        now = int(time.time())
        for bad_sub in [True, False, None, [], {}, "abc", "0", -1, 1.5]:
            with self.subTest(bad_sub=bad_sub):
                token = jwt.encode(
                    {"sub": bad_sub, "iat": now, "exp": now + 300},
                    VALID_SECRET,
                    algorithm="HS256",
                )
                self.assertIsNone(security.decode_access_token(token))

    def test_non_string_sub_rejected(self):
        now = int(time.time())
        token = jwt.encode(
            {"sub": 1, "iat": now, "exp": now + 300},
            VALID_SECRET,
            algorithm="HS256",
        )
        self.assertIsNone(security.decode_access_token(token))

    def test_verify_password_handles_long_password(self):
        long_password = "A1" + ("x" * 100)
        hashed = security.hash_password("A1shortpass")
        with self.assertRaises(ValueError):
            security.hash_password(long_password)
        self.assertFalse(security.verify_password(long_password, hashed))
        self.assertTrue(security.verify_password("A1shortpass", hashed))

    def test_verify_password_handles_malformed_hash(self):
        self.assertFalse(security.verify_password("A1pass", "not-a-hash"))


class DependencyTests(unittest.TestCase):
    def test_get_current_user_returns_401_for_missing_invalid_and_inactive(self):
        with self.assertRaises(HTTPException) as missing:
            dependencies.get_current_user(None, FakeDB())
        self.assertEqual(missing.exception.status_code, 401)
        self.assertEqual(missing.exception.detail, "Authentication required")
        self.assertEqual(missing.exception.headers["WWW-Authenticate"], "Bearer")

        with patch.object(dependencies, "decode_access_token", return_value=None):
            with self.assertRaises(HTTPException) as invalid:
                dependencies.get_current_user(_credentials(), FakeDB())
        self.assertEqual(invalid.exception.status_code, 401)
        self.assertEqual(invalid.exception.detail, "Invalid or expired token")
        self.assertEqual(invalid.exception.headers["WWW-Authenticate"], "Bearer")

        with patch.object(dependencies, "decode_access_token", return_value="abc"):
            with self.assertRaises(HTTPException) as malformed:
                dependencies.get_current_user(_credentials(), FakeDB())
        self.assertEqual(malformed.exception.status_code, 401)
        self.assertEqual(malformed.exception.detail, "Invalid or expired token")

        inactive = SimpleNamespace(id=1, is_active=False)
        with patch.object(dependencies, "decode_access_token", return_value="1"):
            with self.assertRaises(HTTPException) as deactivated:
                dependencies.get_current_user(_credentials(), FakeDB(inactive))
        self.assertEqual(deactivated.exception.status_code, 401)
        self.assertEqual(deactivated.exception.detail, "User not found or deactivated")
        self.assertEqual(deactivated.exception.headers["WWW-Authenticate"], "Bearer")

    def test_get_current_user_401_includes_www_authenticate(self):
        with patch.object(dependencies, "decode_access_token", return_value="1"):
            with self.assertRaises(HTTPException) as missing_user:
                dependencies.get_current_user(_credentials(), FakeDB())
        self.assertEqual(missing_user.exception.status_code, 401)
        self.assertEqual(missing_user.exception.headers["WWW-Authenticate"], "Bearer")

    def test_optional_dependency_returns_none_for_inactive_user(self):
        inactive = SimpleNamespace(id=1, is_active=False)
        with patch.object(dependencies, "decode_access_token", return_value="1"):
            self.assertIsNone(
                dependencies.get_current_user_optional(_credentials(), FakeDB(inactive))
            )

        with patch.object(dependencies, "decode_access_token", return_value=None):
            self.assertIsNone(
                dependencies.get_current_user_optional(_credentials(), FakeDB())
            )
        self.assertIsNone(dependencies.get_current_user_optional(None, FakeDB()))

    def test_get_current_user_returns_active_user(self):
        active = SimpleNamespace(id=7, is_active=True)
        db = FakeDB(active)
        with patch.object(dependencies, "decode_access_token", return_value="7"):
            result = dependencies.get_current_user(_credentials(), db)
        self.assertIs(result, active)
        self.assertEqual(db.requested_id, 7)


class LoginFlowTests(unittest.TestCase):
    def test_register_schema_rejects_password_over_72_bytes(self):
        long_password = "A1" + ("x" * 100)
        with self.assertRaises(ValidationError):
            RegisterRequest(
                email="user@example.com", password=long_password, name="User"
            )
        with self.assertRaises(ValidationError):
            LoginRequest(email="user@example.com", password=long_password)

    def test_login_unknown_user_still_verifies_dummy_hash(self):
        payload = SimpleNamespace(email="missing@example.com", password="wrong-password")
        with patch.object(auth_routes, "verify_password") as real_verify:
            with patch.object(
                auth_routes, "verify_dummy_password", return_value=False
            ) as dummy_verify:
                with self.assertRaises(HTTPException) as raised:
                    asyncio.run(auth_routes.login(payload, FakeAuthDB()))

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(raised.exception.detail, "Invalid email or password")
        real_verify.assert_not_called()
        dummy_verify.assert_called_once_with("wrong-password")

    def test_login_known_user_uses_stored_hash(self):
        user = SimpleNamespace(
            id=1,
            email="user@example.com",
            hashed_password="stored-hash-value",
            is_active=True,
            profile=None,
        )
        payload = SimpleNamespace(email=user.email, password="correct-password")
        with patch.object(auth_routes, "verify_password", return_value=True) as real_verify:
            with patch.object(auth_routes, "verify_dummy_password") as dummy_verify:
                response = asyncio.run(auth_routes.login(payload, FakeAuthDB(user)))

        self.assertIsInstance(response.access_token, str)
        self.assertEqual(response.token_type, "bearer")
        self.assertGreater(response.expires_in, 0)
        real_verify.assert_called_once_with("correct-password", "stored-hash-value")
        dummy_verify.assert_not_called()

    def test_login_error_does_not_expose_secret_or_hash(self):
        sensitive_hash = "SENSITIVE-HASH-VALUE"
        user = SimpleNamespace(
            email="user@example.com",
            hashed_password=sensitive_hash,
            is_active=True,
            profile=None,
        )
        payload = SimpleNamespace(email=user.email, password="wrong-password")
        with patch.object(auth_routes, "verify_password", return_value=False):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(auth_routes.login(payload, FakeAuthDB(user)))

        self.assertEqual(raised.exception.detail, "Invalid email or password")
        self.assertNotIn(sensitive_hash, str(raised.exception.detail))
        self.assertNotIn(VALID_SECRET, str(raised.exception.detail))


if __name__ == "__main__":
    unittest.main()
