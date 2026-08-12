"""V2 生成任务接口测试 — 提交/SSE 流式/完成衔接/失败/取消/超时（全部 mock agent 与导出）。"""
import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from backend import generate
from backend.main import application

client = TestClient(application)


@pytest.fixture(autouse=True)
def isolate_generate_paths(monkeypatch, tmp_path):
    """隔离生成目录 + 短超时 + 清空任务表。"""
    fake_root = tmp_path / "generate"
    monkeypatch.setattr(generate, "GENERATE_ROOT", fake_root)
    monkeypatch.setattr(generate, "GENERATION_TIMEOUT_SECONDS", 30)
    generate.ACTIVE_TASKS.clear()


def make_agent_stream(events):
    """构造 mock agent SSE 事件流（按事件类型返回）。"""

    async def fake_stream(description, output_dir):
        for event in events:
            yield event

    return fake_stream


def make_async_export(recorder):
    """构造 async export mock，记录调用路径。"""

    async def fake_export(blend_path, output_dir):
        recorder.append(str(blend_path))
        return {"export_hash": "fake", "gltf_output_url": "/static/exports/fake/scene.gltf"}

    return fake_export


def test_generate_creates_task_with_status_file(monkeypatch, tmp_path):
    """POST /api/generate：创建任务目录 + status.json=running + 返回 task_id。"""
    monkeypatch.setattr(generate, "stream_from_agent", make_agent_stream([]))

    response = client.post("/api/generate", json={"description": "一个男人站在广场"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    task_id = body["task_id"]
    status_file = tmp_path / "generate" / "output" / task_id / "status.json"
    assert status_file.exists()
    assert json.loads(status_file.read_text())["status"] == "running"


def test_generate_rejects_second_concurrent_task(monkeypatch):
    """生成中再次提交：409 冲突。"""
    monkeypatch.setattr(
        generate, "stream_from_agent", make_agent_stream([{"type": "text", "content": "工作中"}])
    )
    first = client.post("/api/generate", json={"description": "任务一"}).json()

    second = client.post("/api/generate", json={"description": "任务二"})

    assert second.status_code == 409


def test_generate_stream_delivers_agent_events(monkeypatch, tmp_path):
    """SSE 端点：转发 agent 的文本与工具事件。"""
    events = [
        {"type": "text", "content": "正在解析场景"},
        {"type": "tool", "content": "运行 blender 渲染"},
    ]
    monkeypatch.setattr(generate, "stream_from_agent", make_agent_stream(events))

    task_id = client.post("/api/generate", json={"description": "测试流式"}).json()["task_id"]

    with client.stream("GET", f"/api/generate/{task_id}/stream") as response:
        chunks = [line for line in response.iter_lines() if line]

    assert any("正在解析场景" in chunk for chunk in chunks)
    assert any("运行 blender 渲染" in chunk for chunk in chunks)


def test_generate_success_marks_done_and_exports(monkeypatch, tmp_path):
    """Hermes 完成 + 导出成功：status=done，导出被调用。"""
    completed = [{"type": "done", "content": "scene.blend"}]
    monkeypatch.setattr(generate, "stream_from_agent", make_agent_stream(completed))
    exported = []
    monkeypatch.setattr(generate, "export_scene", make_async_export(exported))
    task_id = client.post("/api/generate", json={"description": "成功场景"}).json()["task_id"]
    # 模拟 Hermes 生成的 scene.blend
    blend_file = tmp_path / "generate" / "output" / task_id / "scene.blend"
    blend_file.write_bytes(b"fake blend")
    asyncio.run(generate.run_generation_task(task_id))

    status_file = tmp_path / "generate" / "output" / task_id / "status.json"
    assert json.loads(status_file.read_text())["status"] == "done"
    assert exported, "导出应被调用"


def test_generate_export_retries_once_on_failure(monkeypatch, tmp_path):
    """导出第一次失败第二次成功：自动重试后仍 done。"""
    completed = [{"type": "done", "content": "scene.blend"}]
    monkeypatch.setattr(generate, "stream_from_agent", make_agent_stream(completed))
    attempts = []

    async def flaky_export(blend_path, output_dir):
        attempts.append(1)
        if len(attempts) < 2:
            raise RuntimeError("导出偶发失败")
        return {"export_hash": "fake", "gltf_output_url": "/static/exports/fake/scene.gltf"}

    monkeypatch.setattr(generate, "export_scene", flaky_export)

    task_id = client.post("/api/generate", json={"description": "重试场景"}).json()["task_id"]
    blend_file = tmp_path / "generate" / "output" / task_id / "scene.blend"
    blend_file.write_bytes(b"fake blend")
    asyncio.run(generate.run_generation_task(task_id))

    status_file = tmp_path / "generate" / "output" / task_id / "status.json"
    assert json.loads(status_file.read_text())["status"] == "done"
    assert len(attempts) == 2


def test_generate_failure_marks_failed_with_error(monkeypatch, tmp_path):
    """agent 流异常：status=failed + error 信息 + 日志文件。"""

    async def failing_stream(description, output_dir):
        raise RuntimeError("Blender 脚本报错: NameError")
        yield  # pragma: no cover

    monkeypatch.setattr(generate, "stream_from_agent", failing_stream)

    task_id = client.post("/api/generate", json={"description": "失败场景"}).json()["task_id"]
    asyncio.run(generate.run_generation_task(task_id))

    status_file = tmp_path / "generate" / "output" / task_id / "status.json"
    status_data = json.loads(status_file.read_text())
    assert status_data["status"] == "failed"
    assert "Blender 脚本报错" in status_data["error"]
    log_file = tmp_path / "generate" / "output" / task_id / "generation.log"
    assert log_file.exists()


def test_generate_stop_cancels_task(monkeypatch, tmp_path):
    """取消：status=cancelled + 残留 blender 清理被调用。"""
    killed = []
    monkeypatch.setattr(
        generate, "kill_blender_processes", lambda output_dir: killed.append(str(output_dir))
    )

    task_id = client.post("/api/generate", json={"description": "取消场景"}).json()["task_id"]

    response = client.post(f"/api/generate/{task_id}/stop")

    assert response.status_code == 200
    status_file = tmp_path / "generate" / "output" / task_id / "status.json"
    assert json.loads(status_file.read_text())["status"] == "cancelled"
    assert killed, "残留清理应被调用"


def test_generate_done_status_contains_shot_metadata(monkeypatch, tmp_path):
    """导出成功：status.json 的 done 状态携带 shot 元数据（gltf URL 等）。"""
    completed = [{"type": "done", "content": "scene.blend"}]
    monkeypatch.setattr(generate, "stream_from_agent", make_agent_stream(completed))
    fake_metadata = {
        "export_hash": "abc123",
        "gltf_output_url": "/static/exports/abc123/scene.gltf",
        "cameras": [{"camera_name": "cam_01"}],
    }
    async def fake_export(blend_path, output_dir):
        return fake_metadata

    monkeypatch.setattr(generate, "export_scene", fake_export)

    task_id = client.post("/api/generate", json={"description": "元数据场景"}).json()["task_id"]
    blend_file = tmp_path / "generate" / "output" / task_id / "scene.blend"
    blend_file.write_bytes(b"fake blend")
    asyncio.run(generate.run_generation_task(task_id))

    status_data = json.loads(
        (tmp_path / "generate" / "output" / task_id / "status.json").read_text()
    )
    assert status_data["status"] == "done"
    assert status_data["shot"]["gltf_output_url"] == "/static/exports/abc123/scene.gltf"


def test_generate_status_endpoint_returns_status_file(monkeypatch, tmp_path):
    """GET /api/generate/{task_id}：返回 status.json 内容（任务完成后可查）。"""
    task_id = client.post("/api/generate", json={"description": "查询状态"}).json()["task_id"]
    (tmp_path / "generate" / "output" / task_id / "status.json").write_text(
        json.dumps({"status": "running"}), encoding="utf-8"
    )

    response = client.get(f"/api/generate/{task_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_generate_timeout_marks_failed(monkeypatch, tmp_path):
    """超时：status=failed(timeout)。"""
    monkeypatch.setattr(generate, "GENERATION_TIMEOUT_SECONDS", 0.1)

    async def slow_stream(description, output_dir):
        await asyncio.sleep(5)
        yield {"type": "text", "content": "太慢了"}

    monkeypatch.setattr(generate, "stream_from_agent", slow_stream)

    task_id = client.post("/api/generate", json={"description": "超时场景"}).json()["task_id"]
    asyncio.run(generate.run_generation_task(task_id))

    status_file = tmp_path / "generate" / "output" / task_id / "status.json"
    assert json.loads(status_file.read_text())["status"] == "failed"
