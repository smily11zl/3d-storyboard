"""Integration tests for FastAPI endpoints — upload, metadata, static serve, dedup, disk quota."""
import hashlib
import json
import os
import pytest
import pytest_asyncio
import tempfile
import shutil
from httpx import ASGITransport, AsyncClient


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture
def fixture_blend_path():
    """Path to the minimal test .blend with camera + animation."""
    path = os.path.join(PROJECT_ROOT, "backend", "tests", "fixture_minimal.blend")
    assert os.path.isfile(path), f"Fixture missing: {path}"
    return path


@pytest.fixture
def fixture_blend_no_camera_path():
    """Path to the minimal test .blend with no camera."""
    path = os.path.join(PROJECT_ROOT, "backend", "tests", "fixture_no_camera.blend")
    assert os.path.isfile(path), f"Fixture missing: {path}"
    return path


@pytest.fixture
def fixture_blend_content(fixture_blend_path):
    """Raw bytes of the fixture .blend file."""
    with open(fixture_blend_path, "rb") as file_handle:
        return file_handle.read()


@pytest.fixture
def temporary_export_root():
    """Temporary directory as EXPORTS_ROOT, cleaned up after test."""
    temp_root = tempfile.mkdtemp(prefix="test_exports_")
    yield temp_root
    shutil.rmtree(temp_root, ignore_errors=True)


@pytest_asyncio.fixture
async def async_client(temporary_export_root):
    """Async HTTP client pointed at the FastAPI app with a temp exports root."""
    os.environ["EXPORTS_ROOT"] = temporary_export_root
    os.environ["MAX_DISK_MB"] = "500"
    # Import after env is set so the app module picks up the right paths
    from backend.main import application
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_upload_blend_returns_correct_shape(async_client, fixture_blend_path):
    """Upload a valid .blend → returns JSON with all expected fields."""
    with open(fixture_blend_path, "rb") as file_handle:
        response = await async_client.post(
            "/api/shots",
            files={"file": ("test.blend", file_handle, "application/octet-stream")},
        )

    assert response.status_code == 200, f"Status {response.status_code}: {response.text}"
    data = response.json()

    # Required fields
    assert "export_hash" in data
    assert "gltf_output_url" in data
    assert "cameras" in data
    assert "animations" in data
    assert "duration_seconds" in data
    assert "frames_per_second" in data

    # Camera data
    assert isinstance(data["cameras"], list)
    assert len(data["cameras"]) >= 1
    assert "camera_name" in data["cameras"][0]

    # Animation data
    assert isinstance(data["animations"], list)
    assert len(data["animations"]) >= 1
    assert "animation_name" in data["animations"][0]
    assert "animation_length_seconds" in data["animations"][0]

    # gltf url is accessible
    gltf_path = data["gltf_output_url"].lstrip("/")
    static_response = await async_client.get(f"/{gltf_path}")
    assert static_response.status_code == 200, f"Cannot fetch {gltf_path}"


@pytest.mark.asyncio
async def test_upload_no_camera_blend_returns_empty_cameras(async_client, fixture_blend_no_camera_path):
    """Upload a .blend with no camera → cameras list is empty."""
    with open(fixture_blend_no_camera_path, "rb") as file_handle:
        response = await async_client.post(
            "/api/shots",
            files={"file": ("test_no_camera.blend", file_handle, "application/octet-stream")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["cameras"] == []


@pytest.mark.asyncio
async def test_upload_duplicate_uses_cache(async_client, fixture_blend_path):
    """Upload same .blend twice → second call returns cached result (same hash)."""
    with open(fixture_blend_path, "rb") as file_handle:
        content = file_handle.read()

    response_first = await async_client.post(
        "/api/shots",
        files={"file": ("test.blend", content, "application/octet-stream")},
    )
    assert response_first.status_code == 200
    first_hash = response_first.json()["export_hash"]

    response_second = await async_client.post(
        "/api/shots",
        files={"file": ("test_dup.blend", content, "application/octet-stream")},
    )
    assert response_second.status_code == 200
    second_hash = response_second.json()["export_hash"]

    assert first_hash == second_hash, "Duplicate upload should return same hash"


@pytest.mark.asyncio
async def test_get_shot_metadata(async_client, fixture_blend_content):
    """GET /api/shots/{hash} returns same data as POST."""
    upload_response = await async_client.post(
        "/api/shots",
        files={"file": ("test.blend", fixture_blend_content, "application/octet-stream")},
    )
    assert upload_response.status_code == 200
    upload_data = upload_response.json()
    export_hash = upload_data["export_hash"]

    metadata_response = await async_client.get(f"/api/shots/{export_hash}")
    assert metadata_response.status_code == 200
    assert metadata_response.json()["export_hash"] == export_hash
    assert metadata_response.json()["cameras"] == upload_data["cameras"]


@pytest.mark.asyncio
async def test_get_nonexistent_shot_returns_404(async_client):
    """GET /api/shots/nonexistent → 404."""
    response = await async_client.get("/api/shots/nonexistent_hash")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_upload_non_blend_returns_422(async_client):
    """Upload a .txt file → rejected."""
    response = await async_client.post(
        "/api/shots",
        files={"file": ("not_a_blend.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_disk_quota_eviction(async_client, fixture_blend_content, temporary_export_root):
    """Small disk quota → old files evicted."""
    os.environ["MAX_DISK_MB"] = "1"

    # Upload first file
    response = await async_client.post(
        "/api/shots",
        files={"file": ("first.blend", fixture_blend_content, "application/octet-stream")},
    )
    assert response.status_code == 200

    # Fill up disk to trigger eviction by writing a large dummy file
    dummy_path = os.path.join(temporary_export_root, "dummy_large.bin")
    with open(dummy_path, "wb") as file_handle:
        file_handle.write(b"x" * (2 * 1024 * 1024))  # 2MB > 1MB quota

    # Upload again — should trigger eviction and succeed
    response = await async_client.post(
        "/api/shots",
        files={"file": ("second.blend", fixture_blend_content, "application/octet-stream")},
    )
    # Should succeed because eviction clears space
    assert response.status_code == 200
