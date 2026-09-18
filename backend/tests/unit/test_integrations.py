"""Unit tests for integration service — credential encryption, CRUD, and connection tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.models.integration import Integration
from app.services.integration_service import IntegrationService, SENSITIVE_FIELDS
from app.utils.encryption import encrypt, decrypt


class TestCredentialEncryption:
    def test_sensitive_fields_encrypted(self):
        svc = IntegrationService(MagicMock())
        creds = {"access_key": "AKID123", "region": "us-east-1"}
        encrypted = svc._encrypt_credentials(creds)
        assert encrypted["access_key"] != "AKID123"
        assert encrypted["region"] == "us-east-1"

    def test_decryption_round_trip(self):
        svc = IntegrationService(MagicMock())
        original = {"token": "secret_token_abc", "url": "https://example.com"}
        encrypted = svc._encrypt_credentials(original)
        decrypted = svc._decrypt_credentials(encrypted)
        assert decrypted["token"] == "secret_token_abc"
        assert decrypted["url"] == "https://example.com"

    def test_all_sensitive_fields_covered(self):
        required = {"access_key", "secret_key", "token", "password", "private_key", "api_key", "webhook_secret"}
        assert required.issubset(set(SENSITIVE_FIELDS))

    def test_empty_sensitive_value_not_encrypted(self):
        svc = IntegrationService(MagicMock())
        creds = {"token": "", "url": "http://x.com"}
        encrypted = svc._encrypt_credentials(creds)
        assert encrypted["token"] == ""

    def test_non_sensitive_not_encrypted(self):
        svc = IntegrationService(MagicMock())
        creds = {"region": "eu-west-1", "cluster_name": "prod"}
        encrypted = svc._encrypt_credentials(creds)
        assert encrypted == creds


class TestIntegrationCreate:
    @pytest.mark.asyncio
    async def test_create_integration_success(self):
        from app.schemas.integration import IntegrationCreate
        from datetime import datetime, timezone
        db = MagicMock()
        db.add = MagicMock()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        execute_result.scalars.return_value.first.return_value = None  # singleton branch: no existing
        db.execute = AsyncMock(return_value=execute_result)

        created = {}

        async def _flush():
            obj = db.add.call_args.args[0]
            obj.id = "int-new"
            obj.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
            obj.updated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
            obj.last_sync = None
            obj.error_message = None
            if obj.is_active is None:
                obj.is_active = True  # mirrors the SQLAlchemy INSERT default
        db.flush = AsyncMock(side_effect=_flush)

        svc = IntegrationService(db)
        data = IntegrationCreate(name="My AWS", type="aws", credentials={"access_key": "AKID123"})
        result = await svc.create("tenant-abc", data)
        db.add.assert_called_once()
        assert result.name == "My AWS"
        assert result.type == "aws"
        # credentials encrypted at rest
        obj = db.add.call_args.args[0]
        assert obj.credentials["access_key"] != "AKID123"

    @pytest.mark.asyncio
    async def test_duplicate_integration_raises(self):
        from app.schemas.integration import IntegrationCreate
        from app.core.exceptions import ConflictError
        db = MagicMock()
        db.execute = AsyncMock()

        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = MagicMock(id="existing-id")
        execute_result.scalars.return_value.first.return_value = None  # singleton branch: no existing of same type
        db.execute = AsyncMock(return_value=execute_result)

        svc = IntegrationService(db)
        with pytest.raises(ConflictError):
            await svc.create(
                "tenant-abc",
                IntegrationCreate(name="Duplicate AWS", type="aws", credentials={})
            )

    @pytest.mark.asyncio
    async def test_create_github_upserts_existing_integration(self):
        from app.schemas.integration import IntegrationCreate
        db = MagicMock()
        db.execute = AsyncMock()
        db.flush = AsyncMock()
        db.add = MagicMock()

        integration = Integration()
        integration.id = "existing-github"
        integration.tenant_id = "tenant-abc"
        integration.name = "GitHub"
        integration.type = "github"
        integration.status = "pending"
        integration.is_active = False
        integration.credentials = {"token": "old-token"}
        integration.config = {"repo_count": 1}

        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = integration
        execute_result.scalars.return_value.first.return_value = integration  # singleton branch hit
        db.execute = AsyncMock(return_value=execute_result)

        from datetime import datetime, timezone
        integration.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        integration.updated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        integration.last_sync = None
        integration.error_message = None

        svc = IntegrationService(db)
        data = IntegrationCreate(name="GitHub", type="github", credentials={"token": "new-token"})
        result = await svc.create("tenant-abc", data)

        assert result.id == "existing-github"
        decrypted = svc._decrypt_credentials(integration.credentials)
        assert decrypted["token"] == "new-token"
        assert integration.is_active is True
        assert integration.status == "pending"
        db.add.assert_not_called()


class TestIntegrationGetClient:
    def test_get_aws_client(self):
        svc = IntegrationService(MagicMock())
        from app.integrations.aws.client import AWSClient
        client = svc._build_client("aws", {}, {})
        assert isinstance(client, AWSClient)

    def test_get_gitlab_client(self):
        svc = IntegrationService(MagicMock())
        from app.integrations.gitlab.client import GitLabClient
        client = svc._build_client("gitlab", {}, {})
        assert isinstance(client, GitLabClient)

    def test_unknown_type_returns_dummy(self):
        # BUG-P2-03: the silent "dummy/NoOp" client (fake-success stub) was
        # deleted.  Unknown types now raise — see SUPPORTED_INTEGRATION_TYPES.
        import pytest
        svc = IntegrationService(MagicMock())
        with pytest.raises(ValueError, match="Unsupported integration type"):
            svc._build_client("unknown_type", {}, {})
