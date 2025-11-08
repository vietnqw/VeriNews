"""
Unit tests for Health Check API endpoints.

Tests health check endpoints with various scenarios including
database connectivity and pgvector extension availability.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.health import router


@pytest.mark.unit
class TestHealthAPI:
    """Unit tests for health check API."""

    @pytest.fixture
    def app(self):
        """Create FastAPI app with health router."""
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        mock = AsyncMock(spec=AsyncSession)
        return mock

    # ==================== Simple Health Check Tests ====================

    def test_simple_health_check_success(self, client):
        """Test simple health check without database dependency."""
        response = client.get("/health/simple")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_simple_health_check_structure(self, client):
        """Test simple health check response structure."""
        response = client.get("/health/simple")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "status" in data

    # ==================== Full Health Check Tests ====================

    @pytest.mark.asyncio
    async def test_health_check_all_healthy(self, app, mock_db_session):
        """Test health check when all systems are healthy."""
        # Mock database connection check
        mock_result_1 = MagicMock()
        mock_result_1.scalar.return_value = 1

        # Mock pgvector version check
        mock_result_2 = MagicMock()
        mock_result_2.scalar.return_value = "0.5.0"

        mock_db_session.execute = AsyncMock(side_effect=[mock_result_1, mock_result_2])

        # Override dependency
        def override_get_db():
            yield mock_db_session

        from app.config.database import get_db

        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["api"] == "running"
        assert data["database"] == "connected"
        assert "available" in data["pgvector"]
        assert "0.5.0" in data["pgvector"]

    @pytest.mark.asyncio
    async def test_health_check_database_connected_no_pgvector(
        self, app, mock_db_session
    ):
        """Test health check when database is connected but pgvector is unavailable."""
        # Mock database connection check
        mock_result_1 = MagicMock()
        mock_result_1.scalar.return_value = 1

        # Mock pgvector version check (not installed)
        mock_result_2 = MagicMock()
        mock_result_2.scalar.return_value = None

        mock_db_session.execute = AsyncMock(side_effect=[mock_result_1, mock_result_2])

        def override_get_db():
            yield mock_db_session

        from app.config.database import get_db

        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["pgvector"] == "unavailable"

    @pytest.mark.asyncio
    async def test_health_check_database_error(self, app, mock_db_session):
        """Test health check when database connection fails."""
        # Mock database connection failure
        mock_db_session.execute = AsyncMock(side_effect=Exception("Connection refused"))

        def override_get_db():
            yield mock_db_session

        from app.config.database import get_db

        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)
        response = client.get("/health")

        assert (
            response.status_code == 200
        )  # Still returns 200 but with unhealthy status
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
        assert "error" in data
        assert "Connection refused" in data["error"]

    @pytest.mark.asyncio
    async def test_health_check_response_structure(self, app, mock_db_session):
        """Test health check response has correct structure."""
        mock_result_1 = MagicMock()
        mock_result_1.scalar.return_value = 1
        mock_result_2 = MagicMock()
        mock_result_2.scalar.return_value = "0.5.0"

        mock_db_session.execute = AsyncMock(side_effect=[mock_result_1, mock_result_2])

        def override_get_db():
            yield mock_db_session

        from app.config.database import get_db

        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)
        response = client.get("/health")

        data = response.json()
        required_fields = ["status", "api", "database", "pgvector"]
        for field in required_fields:
            assert field in data

    @pytest.mark.asyncio
    async def test_health_check_database_timeout(self, app, mock_db_session):
        """Test health check when database query times out."""
        import asyncio

        mock_db_session.execute = AsyncMock(
            side_effect=asyncio.TimeoutError("Query timeout")
        )

        def override_get_db():
            yield mock_db_session

        from app.config.database import get_db

        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "error" in data

    # ==================== Edge Case Tests ====================

    def test_health_check_multiple_calls(self, client):
        """Test simple health check can be called multiple times."""
        for _ in range(5):
            response = client.get("/health/simple")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_check_pgvector_different_versions(self, app, mock_db_session):
        """Test health check with different pgvector versions."""
        versions = ["0.4.0", "0.5.1", "0.6.0-beta"]

        for version in versions:
            mock_result_1 = MagicMock()
            mock_result_1.scalar.return_value = 1
            mock_result_2 = MagicMock()
            mock_result_2.scalar.return_value = version

            mock_db_session.execute = AsyncMock(
                side_effect=[mock_result_1, mock_result_2]
            )

            def override_get_db():
                yield mock_db_session

            from app.config.database import get_db

            app.dependency_overrides[get_db] = override_get_db

            client = TestClient(app)
            response = client.get("/health")

            data = response.json()
            assert data["status"] == "healthy"
            assert version in data["pgvector"]

    # ==================== Concurrent Request Tests ====================

    def test_simple_health_concurrent_requests(self, client):
        """Test simple health check handles concurrent requests."""
        import concurrent.futures

        def make_request():
            response = client.get("/health/simple")
            return response.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert all(status == 200 for status in results)
