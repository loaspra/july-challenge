"""Authentication tests for API key security."""
import io
import pytest

# List of (endpoint, method, kwargs) tuples for parameterization
PROTECTED_REQUESTS = [
    ("/api/v1/batch/departments", "post", {
        "json": {
            "table": "departments",
            "rows": [{"id": 99, "department": "TestDept"}]
        }
    }),
    ("/api/v1/upload/csv/departments", "post", {
        "files": {
            "file": ("departments.csv", io.BytesIO(b"id,department\n1,Hello"), "text/csv")
        }
    }),
    ("/api/v1/analytics/hired/by-quarter?year=2021", "get", {}),
]


@pytest.mark.parametrize("url,method,kwargs", PROTECTED_REQUESTS)
def test_missing_api_key(client, url, method, kwargs):
    """Requests made without an API key header should be rejected with 403."""
    client.headers.pop("X-API-Key", None)
    response = getattr(client, method)(url, **kwargs)
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.parametrize("url,method,kwargs", PROTECTED_REQUESTS)
def test_invalid_api_key(client, url, method, kwargs):
    """Requests made with an invalid API key should be rejected with 403."""
    client.headers.update({"X-API-Key": "invalid-key"})
    response = getattr(client, method)(url, **kwargs)
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authenticated"
