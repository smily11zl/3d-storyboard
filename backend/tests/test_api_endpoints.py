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
async def async_client(temporary_export_root, monkeypatch, tmp_path):
    """Async HTTP client pointed at the FastAPI app with temp exports + generate roots."""
    os.environ["EXPORTS_ROOT"] = temporary_export_root
    os.environ["MAX_DISK_MB"] = "500"
    from backend import generate

    monkeypatch.setattr(generate, "GENERATE_ROOT", tmp_path / "generate")
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


@pytest.mark.asyncio
async def test_ingest_blend_exports_without_blend_and_with_source(monkeypatch, tmp_path, fixture_blend_path):
    """ingest_blend 只写渲染产物（不保留 blend），且 metadata 记录 source。"""
    from backend import main as main_module

    monkeypatch.setattr(main_module, "EXPORTS_ROOT", tmp_path / "exports")
    (tmp_path / "exports").mkdir(parents=True, exist_ok=True)

    metadata = await main_module.ingest_blend(
        fixture_blend_path,
        source={"type": "upload", "file": "20260821_131503.blend"},
    )

    export_dir = tmp_path / "exports" / metadata["export_hash"]
    assert (export_dir / "scene.gltf").is_file(), "exports 应包含渲染产物 scene.gltf"
    blends = list(export_dir.glob("*.blend"))
    assert blends == [], "exports 不应保留任何 blend（源由调用方管理）"
    assert metadata["source"] == {"type": "upload", "file": "20260821_131503.blend"}


@pytest.mark.asyncio
async def test_export_scene_writes_chat_source(monkeypatch, tmp_path, fixture_blend_path):
    """export_scene（切换聊天 reload）应把 source 记为 chat + folder。"""
    from pathlib import Path

    from backend import generate
    from backend import main as main_module

    monkeypatch.setattr(main_module, "EXPORTS_ROOT", tmp_path / "exports")
    (tmp_path / "exports").mkdir(parents=True, exist_ok=True)

    async def fake_run_export(blend_path, output_directory):
        os.makedirs(output_directory, exist_ok=True)
        with open(os.path.join(output_directory, "scene.gltf"), "w") as file_handle:
            file_handle.write('{"asset":{"version":"2.0"}}')

    monkeypatch.setattr(main_module, "run_export", fake_run_export)
    monkeypatch.setattr(
        main_module,
        "build_shot_metadata",
        lambda export_hash, export_directory, gltf: {"export_hash": export_hash},
    )
    monkeypatch.setattr(main_module, "save_shot_metadata", lambda export_hash, metadata: None)
    monkeypatch.setattr(main_module, "enforce_disk_quota", lambda: None)

    folder = tmp_path / "20260817_115113"
    metadata = await generate.export_scene(Path(fixture_blend_path), folder)

    assert metadata["source"] == {"type": "chat", "folder": "20260817_115113"}


def _valid_segment():
    return {
        "camera_name": "cam_01",
        "segment_name": "seg_01",
        "start_time": 0.0,
        "end_time": 3.0,
        "start_pose": {"position": [0, 1, 2], "rotation": [0, 0, 0]},
        "end_pose": {"position": [2, 1, 2], "rotation": [0, 0, 0]},
    }


def _mock_apply_and_export(monkeypatch, main_module):
    """mock run_apply_edit（复制输入到输出）+ run_export（生成假 gltf）+ build_shot_metadata。"""

    async def fake_apply_edit(input_blend, operations_file, output_blend):
        shutil.copy(input_blend, output_blend)

    async def fake_run_export(blend_path, output_directory):
        os.makedirs(output_directory, exist_ok=True)
        with open(os.path.join(output_directory, "scene.gltf"), "w") as file_handle:
            file_handle.write('{"asset":{"version":"2.0"}}')

    monkeypatch.setattr(main_module, "run_apply_edit", fake_apply_edit)
    monkeypatch.setattr(main_module, "run_export", fake_run_export)
    monkeypatch.setattr(
        main_module,
        "build_shot_metadata",
        lambda export_hash, export_directory, gltf: {"export_hash": export_hash},
    )


@pytest.mark.asyncio
async def test_edit_shot_chat_source_writes_scene_v2(monkeypatch, tmp_path):
    """聊天源保存：读 generate/output/<folder>/ 最新 blend，写回 scene_v2.blend，source 不变。"""
    from backend import generate
    from backend import main as main_module
    from backend.main import EditRequest

    exports_root = tmp_path / "exports"
    exports_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(main_module, "EXPORTS_ROOT", exports_root)
    monkeypatch.setattr(generate, "GENERATE_ROOT", tmp_path / "generate")

    folder = tmp_path / "generate" / "output" / "20260817_115113"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "scene.blend").write_bytes(b"fake chat blend")

    export_hash = "a" * 64
    export_dir = exports_root / export_hash
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "shot_metadata.json").write_text(
        json.dumps(
            {"export_hash": export_hash, "source": {"type": "chat", "folder": "20260817_115113"}}
        )
    )

    _mock_apply_and_export(monkeypatch, main_module)

    result = await main_module.edit_shot(
        export_hash,
        EditRequest(segments=[_valid_segment()], target_positions={}),
    )

    assert (folder / "scene_v2.blend").is_file(), "聊天源保存应写回 scene_v2.blend"
    assert result["source"] == {"type": "chat", "folder": "20260817_115113"}


@pytest.mark.asyncio
async def test_edit_shot_upload_source_writes_new_upload_output(monkeypatch, tmp_path):
    """上传源保存：读 upload_output/<file>，输出新的 upload_output/<新时间戳>.blend 并更新 source。"""
    from backend import generate
    from backend import main as main_module
    from backend.main import EditRequest

    exports_root = tmp_path / "exports"
    exports_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(main_module, "EXPORTS_ROOT", exports_root)
    monkeypatch.setattr(generate, "GENERATE_ROOT", tmp_path / "generate")

    # 上传源文件：generate/upload_output/<file>.blend
    upload_root = tmp_path / "generate" / "upload_output"
    upload_root.mkdir(parents=True, exist_ok=True)
    source_filename = "20260821_131503_123456.blend"
    (upload_root / source_filename).write_bytes(b"fake upload blend")

    export_hash = "b" * 64
    export_dir = exports_root / export_hash
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "shot_metadata.json").write_text(
        json.dumps(
            {
                "export_hash": export_hash,
                "source": {"type": "upload", "file": source_filename},
            }
        )
    )

    _mock_apply_and_export(monkeypatch, main_module)

    result = await main_module.edit_shot(
        export_hash,
        EditRequest(segments=[_valid_segment()], target_positions={}),
    )

    blends = [p.name for p in upload_root.iterdir() if p.suffix == ".blend"]
    assert len(blends) == 2, f"上传源保存应在 upload_output 新增一个 blend，现有: {blends}"
    assert result["source"]["type"] == "upload"
    assert result["source"]["file"] != source_filename, "保存后 source 应更新为新文件"
    assert (upload_root / result["source"]["file"]).is_file()


@pytest.mark.asyncio
async def test_list_blends_returns_versions_from_source_folder(monkeypatch, tmp_path):
    """list_blends 从源目录读版本（按 mtime 排序），而非 exports。"""
    from backend import generate
    from backend import main as main_module

    exports_root = tmp_path / "exports"
    exports_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(main_module, "EXPORTS_ROOT", exports_root)
    monkeypatch.setattr(generate, "GENERATE_ROOT", tmp_path / "generate")

    folder = tmp_path / "generate" / "output" / "20260817_115113"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "scene.blend").write_bytes(b"original")
    (folder / "scene_v2.blend").write_bytes(b"version two")
    os.utime(folder / "scene.blend", (1000, 1000))
    os.utime(folder / "scene_v2.blend", (2000, 2000))

    export_hash = "c" * 64
    export_dir = exports_root / export_hash
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "shot_metadata.json").write_text(
        json.dumps(
            {"export_hash": export_hash, "source": {"type": "chat", "folder": "20260817_115113"}}
        )
    )

    result = await main_module.list_blends(export_hash)

    filenames = [blend["filename"] for blend in result["blends"]]
    assert filenames == ["scene.blend", "scene_v2.blend"], f"应按 mtime 排序，实际 {filenames}"
    assert result["latest"] == "scene_v2.blend"
    assert all("blend_hash" in blend for blend in result["blends"])


@pytest.mark.asyncio
async def test_upload_writes_source_to_upload_output(
    async_client, fixture_blend_content, tmp_path, monkeypatch
):
    """上传后：源 blend 落 upload_output（扁平 <时间戳>.blend），source 用 file 字段。"""
    from backend import main as main_module

    async def fake_run_export(blend_path, output_directory):
        os.makedirs(output_directory, exist_ok=True)
        with open(os.path.join(output_directory, "scene.gltf"), "w") as file_handle:
            file_handle.write('{"asset":{"version":"2.0"}}')

    monkeypatch.setattr(main_module, "run_export", fake_run_export)
    monkeypatch.setattr(main_module, "EXPORTS_ROOT", tmp_path / "exports")
    (tmp_path / "exports").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        main_module,
        "build_shot_metadata",
        lambda export_hash, export_directory, gltf: {"export_hash": export_hash},
    )

    response = await async_client.post(
        "/api/shots",
        files={"file": ("test.blend", fixture_blend_content, "application/octet-stream")},
    )
    assert response.status_code == 200, response.text

    upload_output = tmp_path / "generate" / "upload_output"
    source_blends = list(upload_output.rglob("*.blend"))
    assert len(source_blends) == 1, f"上传应写 1 个源 blend 到 upload_output，实际 {source_blends}"
    source = response.json()["source"]
    assert source["type"] == "upload"
    assert source["file"].endswith(".blend")


@pytest.mark.asyncio
async def test_reupload_restores_deleted_source(
    async_client, fixture_blend_content, tmp_path, monkeypatch
):
    """删掉源 blend 后重新上传同一 blend，缓存命中时应补回源文件。"""
    from backend import main as main_module

    async def fake_run_export(blend_path, output_directory):
        os.makedirs(output_directory, exist_ok=True)
        with open(os.path.join(output_directory, "scene.gltf"), "w") as file_handle:
            file_handle.write('{"asset":{"version":"2.0"}}')

    monkeypatch.setattr(main_module, "run_export", fake_run_export)
    monkeypatch.setattr(main_module, "EXPORTS_ROOT", tmp_path / "exports")
    (tmp_path / "exports").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        main_module,
        "build_shot_metadata",
        lambda export_hash, export_directory, gltf: {"export_hash": export_hash},
    )

    files = {"file": ("test.blend", fixture_blend_content, "application/octet-stream")}

    first_response = await async_client.post("/api/shots", files=files)
    assert first_response.status_code == 200
    first_metadata = first_response.json()
    source_blend = (
        tmp_path / "generate" / "upload_output" / first_metadata["source"]["file"]
    )

    # 手动删除源 blend
    source_blend.unlink()
    assert not source_blend.exists(), "前置：源 blend 应已删除"

    # 重新上传同一 blend（缓存命中）
    second_response = await async_client.post("/api/shots", files=files)
    assert second_response.status_code == 200

    assert source_blend.is_file(), "重新上传应补回被删的源 blend"


@pytest.mark.asyncio
async def test_reupload_restores_source_when_metadata_has_legacy_folder_field(
    async_client, fixture_blend_content, tmp_path, monkeypatch
):
    """旧 metadata source 用 folder 字段（非 file）时，重传应重建 upload 源为 file 字段。"""
    from backend import main as main_module

    async def fake_run_export(blend_path, output_directory):
        os.makedirs(output_directory, exist_ok=True)
        with open(os.path.join(output_directory, "scene.gltf"), "w") as file_handle:
            file_handle.write('{"asset":{"version":"2.0"}}')

    monkeypatch.setattr(main_module, "run_export", fake_run_export)
    monkeypatch.setattr(main_module, "EXPORTS_ROOT", tmp_path / "exports")
    (tmp_path / "exports").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        main_module,
        "build_shot_metadata",
        lambda export_hash, export_directory, gltf: {"export_hash": export_hash},
    )

    files = {"file": ("test.blend", fixture_blend_content, "application/octet-stream")}

    first_response = await async_client.post("/api/shots", files=files)
    assert first_response.status_code == 200
    first_metadata = first_response.json()
    export_hash = first_metadata["export_hash"]
    old_source_blend = (
        tmp_path / "generate" / "upload_output" / first_metadata["source"]["file"]
    )

    # 删除源 blend + 把 metadata 的 source 改成旧字段 folder（模拟历史数据）
    old_source_blend.unlink()
    metadata = main_module.load_shot_metadata(export_hash)
    assert metadata is not None, "前置：首次上传应写入 metadata"
    metadata["source"] = {"type": "upload", "folder": "20260821_000000_000000"}
    main_module.save_shot_metadata(export_hash, metadata)

    # 重新上传同一 blend（缓存命中，旧字段 folder 无法定位源）
    second_response = await async_client.post("/api/shots", files=files)
    assert second_response.status_code == 200
    second_metadata = second_response.json()

    # 源应被重建为新字段 file
    assert second_metadata["source"]["type"] == "upload"
    assert "file" in second_metadata["source"]
    new_source_blend = (
        tmp_path / "generate" / "upload_output" / second_metadata["source"]["file"]
    )
    assert new_source_blend.is_file(), "旧字段 folder metadata 重传应重建 upload 源"
