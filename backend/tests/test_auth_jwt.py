"""Unit tests for Phase 1 JWT verification and protected routes."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import jwt
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.auth import (
    AuthError,
    auth_is_enforced,
    verify_supabase_access_token,
)
from app.core.supabase_config import SupabaseConfig
from app.deps.auth import require_authenticated_user
from app.routes import videos as videos_routes


_SECRET = "unit-test-jwt-secret-key"
_URL = "https://example.supabase.co"
_USER = "11111111-1111-1111-1111-111111111111"


def _config(**kwargs: object) -> SupabaseConfig:
    return SupabaseConfig(
        url=str(kwargs.get("url", _URL)),
        anon_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.anon-test-key-xx",
        jwt_secret=kwargs.get("jwt_secret", _SECRET),  # type: ignore[arg-type]
        jwks_url=kwargs.get("jwks_url"),  # type: ignore[arg-type]
        service_role_key=None,
        environment="test",
    )


def _token(
    *,
    sub: str = _USER,
    secret: str = _SECRET,
    aud: str = "authenticated",
    iss: str | None = None,
    exp_delta: timedelta = timedelta(hours=1),
    email: str = "user@example.com",
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "email": email,
        "role": "authenticated",
        "aud": aud,
        "iss": iss or f"{_URL}/auth/v1",
        "iat": int(now.timestamp()),
        "exp": int((now + exp_delta).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


class TestVerifySupabaseAccessToken(unittest.TestCase):
    def test_valid_token(self) -> None:
        user = verify_supabase_access_token(_token(), _config())
        self.assertEqual(user.user_id, _USER)
        self.assertEqual(user.email, "user@example.com")
        self.assertEqual(user.role, "authenticated")

    def test_expired_token(self) -> None:
        token = _token(exp_delta=timedelta(hours=-1))
        with self.assertRaises(AuthError) as ctx:
            verify_supabase_access_token(token, _config())
        self.assertIn("expired", ctx.exception.detail.lower())

    def test_wrong_secret(self) -> None:
        with self.assertRaises(AuthError):
            verify_supabase_access_token(
                _token(secret="wrong-secret-key!!"),
                _config(),
            )

    def test_missing_token(self) -> None:
        with self.assertRaises(AuthError):
            verify_supabase_access_token("", _config())

    def test_wrong_audience(self) -> None:
        with self.assertRaises(AuthError):
            verify_supabase_access_token(_token(aud="anon"), _config())


class TestAuthEnforced(unittest.TestCase):
    def test_auth_disabled_in_development(self) -> None:
        from app.core.config import Settings

        settings = Settings.model_construct(
            app_name="t",
            app_env="development",
            auth_disabled=True,
            log_level="INFO",
            cors_origins=[],
        )
        with mock.patch("app.core.auth.load_supabase_config", return_value=_config()):
            self.assertFalse(auth_is_enforced(settings))

    def test_auth_disabled_ignored_in_production(self) -> None:
        from app.core.config import Settings

        settings = Settings.model_construct(
            app_name="t",
            app_env="production",
            auth_disabled=True,
            log_level="INFO",
            cors_origins=[],
        )
        with mock.patch("app.core.auth.load_supabase_config", return_value=_config()):
            self.assertTrue(auth_is_enforced(settings))


class TestProtectedRoutes(unittest.TestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(videos_routes.router)
        self.client = TestClient(self.app)
        self._job = {
            "job_id": "12345678-1234-1234-1234-123456789012",
            "status": "queued",
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "video_path": None,
            "curated_json_path": None,
            "output_clip_paths": None,
            "error": None,
            "stage": None,
        }

    def _enforce_auth(self) -> mock._patch:
        return mock.patch(
            "app.deps.auth.auth_is_enforced",
            return_value=True,
        )

    def _supabase(self) -> mock._patch:
        return mock.patch(
            "app.deps.auth.load_supabase_config",
            return_value=_config(),
        )

    def test_missing_token_returns_401(self) -> None:
        with self._enforce_auth(), self._supabase():
            response = self.client.post(
                "/api/process-video",
                json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Not authenticated")

    def test_invalid_token_returns_401(self) -> None:
        with self._enforce_auth(), self._supabase():
            response = self.client.post(
                "/api/process-video",
                json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
                headers={"Authorization": "Bearer not-a-real-jwt"},
            )
        self.assertEqual(response.status_code, 401)

    def test_valid_token_allows_process_video(self) -> None:
        token = _token()
        with (
            self._enforce_auth(),
            self._supabase(),
            mock.patch(
                "app.routes.videos.job_store.create_job",
                return_value=self._job,
            ),
            mock.patch("app.routes.videos.process_video_job"),
        ):
            response = self.client.post(
                "/api/process-video",
                json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
                headers={"Authorization": f"Bearer {token}"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job_id"], self._job["job_id"])

    def test_valid_token_allows_get_job(self) -> None:
        token = _token()
        with (
            self._enforce_auth(),
            self._supabase(),
            mock.patch(
                "app.routes.videos.job_store.get_job",
                return_value=self._job,
            ),
        ):
            response = self.client.get(
                f"/api/jobs/{self._job['job_id']}",
                headers={"Authorization": f"Bearer {token}"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "queued")

    def test_dependency_returns_user_identity(self) -> None:
        mini = FastAPI()

        @mini.get("/me")
        async def me_route(
            user=Depends(require_authenticated_user),  # noqa: B008
        ):
            return {"user_id": user.user_id, "email": user.email}

        client = TestClient(mini)
        token = _token()
        with self._enforce_auth(), self._supabase():
            response = client.get(
                "/me",
                headers={"Authorization": f"Bearer {token}"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user_id"], _USER)
        self.assertEqual(response.json()["email"], "user@example.com")


if __name__ == "__main__":
    unittest.main()
