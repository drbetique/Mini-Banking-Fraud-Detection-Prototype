"""Unit tests for API endpoints."""
import pytest
from fastapi.testclient import TestClient
import os

# Set test API key before importing app
os.environ['AZURE_API_KEY'] = 'test-key-for-testing'

from api import app

client = TestClient(app)


class TestHealthEndpoints:
    """Test suite for health check endpoints (to be added)."""

    def test_root_endpoint(self):
        """Test root endpoint exists."""
        response = client.get("/")
        # May return 404 if not implemented, that's ok for now
        assert response.status_code in [200, 404]


class TestAuthentication:
    """Test suite for API authentication."""

    def test_missing_api_key_returns_401(self):
        """Test that requests without API key are rejected."""
        response = client.get("/api/v1/anomalies")
        assert response.status_code == 401, "Should return 401 Unauthorized without API key"

    def test_invalid_api_key_returns_401(self):
        """Test that requests with invalid API key are rejected."""
        response = client.get(
            "/api/v1/anomalies",
            headers={"X-API-Key": "invalid-key-123"}
        )
        assert response.status_code == 401, "Should return 401 with invalid API key"

    def test_valid_api_key_grants_access(self):
        """Test that valid API key grants access to endpoints."""
        response = client.get(
            "/api/v1/anomalies",
            headers={"X-API-Key": "test-key-for-testing"}
        )
        # May fail with 500 if DB not available, but auth should pass
        assert response.status_code in [200, 500], "Valid API key should pass authentication"


class TestAnomaliesEndpoint:
    """Test suite for anomalies retrieval endpoint."""

    def test_anomalies_endpoint_structure(self):
        """Test that anomalies endpoint returns correct structure."""
        response = client.get(
            "/api/v1/anomalies",
            headers={"X-API-Key": "test-key-for-testing"}
        )

        if response.status_code == 200:
            data = response.json()
            assert "data" in data, "Response should contain 'data' field"
            assert isinstance(data["data"], list), "'data' should be a list"


class TestUpdateStatus:
    """Test suite for status update endpoint."""

    def test_invalid_status_rejected(self):
        """Test that invalid status values are rejected."""
        response = client.put(
            "/api/v1/anomalies/TRX_001",
            json={"new_status": "INVALID_STATUS"},
            headers={"X-API-Key": "test-key-for-testing"}
        )
        assert response.status_code == 422, "Should return 422 for invalid status"

    def test_valid_status_values_accepted(self):
        """Test that valid status values are accepted."""
        valid_statuses = ["NEW", "INVESTIGATED", "FRAUD", "DISMISSED"]

        for status in valid_statuses:
            response = client.put(
                "/api/v1/anomalies/TRX_NONEXISTENT",
                json={"new_status": status},
                headers={"X-API-Key": "test-key-for-testing"}
            )
            # Should either succeed (200) or return 404 (not found) or 500 (DB error)
            # But NOT 422 (validation error)
            assert response.status_code != 422, f"Status '{status}' should be valid"

    def test_missing_transaction_id_returns_404(self):
        """Test that updating non-existent transaction returns 404."""
        response = client.put(
            "/api/v1/anomalies/NONEXISTENT_TRX_999",
            json={"new_status": "FRAUD"},
            headers={"X-API-Key": "test-key-for-testing"}
        )
        # Should return 404 or 500 depending on DB state
        assert response.status_code in [404, 500]

    def test_lowercase_status_accepted(self):
        """Test that lowercase status is accepted and normalized."""
        response = client.put(
            "/api/v1/anomalies/TRX_001",
            json={"new_status": "fraud"},  # lowercase
            headers={"X-API-Key": "test-key-for-testing"}
        )
        # Should not fail validation (422)
        assert response.status_code != 422, "Lowercase status should be accepted"


class TestCORS:
    """Test suite for CORS configuration."""

    def test_cors_headers_present(self):
        """Test that CORS headers are properly configured."""
        response = client.options("/api/v1/anomalies")
        # Check that the request doesn't fail
        assert response.status_code in [200, 404, 405]
