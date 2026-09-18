"""P1.6 config-gate pins — CORS default must never allow credentialed wildcard."""


def test_cors_default_is_explicit_origins_not_wildcard():
    from app.config import Settings
    default = Settings.model_fields["CORS_ORIGINS"].default
    assert "*" not in default, f"unsafe credentialed wildcard default: {default}"
    assert default, "default origins must exist for local dev"


def test_secret_key_placeholder_default_is_rejected():
    import pytest
    from app.config import Settings
    with pytest.raises(Exception):
        # class-level validator must refuse the placeholder default outright
        Settings(SECRET_KEY="change-me-in-production", DATABASE_URL="sqlite+aiosqlite:///:memory:")


def test_cors_wildcard_is_dropped_when_credentials_enabled():
    """P1.6-CORS-2: even in dev/test, CORS_ORIGINS=['*'] must never survive —
    with allow_credentials=True Starlette would echo ANY caller origin with
    credentialed access.  The Settings validator must strip the wildcard."""
    from app.config import Settings
    s = Settings(
        SECRET_KEY="gate-" + "a1" * 32,
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        CORS_ORIGINS=["*", "http://localhost:5173"],
    )
    assert "*" not in s.CORS_ORIGINS, f"wildcard survived: {s.CORS_ORIGINS}"
    assert "http://localhost:5173" in s.CORS_ORIGINS
