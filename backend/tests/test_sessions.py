"""V3 会话历史接口测试 — 转发 Hermes /api/sessions + 转换层 + 打开 Finder（全部 mock）。"""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import sessions
from backend.main import application

client = TestClient(application)


@pytest.fixture(autouse=True)
def isolate_output_root(monkeypatch, tmp_path):
    """隔离输出目录，避免污染项目真实 generate/output。"""
    monkeypatch.setattr(sessions, "GENERATE_OUTPUT_ROOT", tmp_path / "output")


# ── 转换层单测 ─────────────────────────────────────────────────────────────

def test_convert_hermes_messages_full_chain():
    """user/assistant 文本/工具调用/tool 输出 → 前端 UI 格式。"""
    hermes_messages = [
        {"role": "user", "content": "两个男人对峙"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "skill_view", "arguments": '{"name": "storyboard-scene-generator"}'}},
                {"function": {"name": "terminal", "arguments": '{"command": "pwd"}'}},
            ],
        },
        {"role": "tool", "content": '{"success": true, "output": "/Users/zengle"}'},
        {"role": "assistant", "content": "场景已生成，cam_01 就位。"},
    ]

    result = sessions.convert_hermes_messages(hermes_messages)

    assert result == [
        {"role": "user", "content": "两个男人对峙"},
        {"role": "tool_start", "name": "skill_view", "content": '{"name": "storyboard-scene-generator"}'},
        {"role": "tool_start", "name": "terminal", "content": '{"command": "pwd"}'},
        {"role": "tool_output", "content": '{"success": true, "output": "/Users/zengle"}'},
        {"role": "agent", "content": "场景已生成，cam_01 就位。"},
    ]


def test_convert_hermes_messages_truncates_long_content():
    """tool_output 超长截断到 150 字符，tool_start 参数截断到 120 字符。"""
    hermes_messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": "terminal", "arguments": "x" * 300}}],
        },
        {"role": "tool", "content": "y" * 300},
    ]

    result = sessions.convert_hermes_messages(hermes_messages)

    assert len(result[0]["content"]) == 120
    assert len(result[1]["content"]) == 150


def test_convert_hermes_messages_handles_string_tool_calls():
    """tool_calls 为 JSON 字符串时也能解析。"""
    hermes_messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": json.dumps([{"function": {"name": "terminal", "arguments": "{}"}}]),
        }
    ]
    result = sessions.convert_hermes_messages(hermes_messages)
    assert result == [{"role": "tool_start", "name": "terminal", "content": "{}"}]


def test_convert_hermes_messages_extracts_reasoning():
    """assistant 的 reasoning 字段 → 独立的 reasoning 消息（在 agent 文本之前）。"""
    hermes_messages = [
        {"role": "assistant", "reasoning": "先加载 skill 看看", "content": "好的"},
    ]
    result = sessions.convert_hermes_messages(hermes_messages)
    assert result == [
        {"role": "reasoning", "content": "先加载 skill 看看"},
        {"role": "agent", "content": "好的"},
    ]


# ── 端点测试 ───────────────────────────────────────────────────────────────

def _hermes_response(status_code, body):
    return httpx.Response(status_code, json=body)


def test_list_sessions_attaches_folder_and_preview(monkeypatch, tmp_path):
    """历史列表：附加文件夹名 + 预览 + 输出存在性，过滤非 api_server。"""
    # 建输出文件夹 + status.json 带 session_id（精确映射）
    output_root = tmp_path / "output"
    folder = output_root / "20260814_075856"
    folder.mkdir(parents=True)
    (folder / "status.json").write_text(json.dumps({"session_id": "sid-aaa"}))

    async def fake_forward(method, path):
        assert method == "GET"
        assert path == "/api/sessions"
        return _hermes_response(200, {
            "object": "list",
            "data": [
                {
                    "id": "sid-aaa",
                    "source": "api_server",
                    "started_at": 1786665538.0,
                    "preview": "两个男人对峙",
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "estimated_cost_usd": 0.01,
                    "message_count": 5,
                },
                {
                    "id": "sid-cli",
                    "source": "cli",  # 非 api_server，应被过滤
                    "preview": "本地会话",
                },
            ],
        })

    monkeypatch.setattr(sessions, "forward_to_hermes", fake_forward)

    response = client.get("/api/sessions")

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    session = body["data"][0]
    assert session["id"] == "sid-aaa"
    assert session["folder_name"] == "20260814_075856"
    assert session["preview"] == "两个男人对峙"
    assert session["has_output"] is True
    assert session["input_tokens"] == 100


def test_list_sessions_hermes_down_returns_502(monkeypatch):
    """Hermes 不可用：返回 502。"""
    async def fake_forward(method, path):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(sessions, "forward_to_hermes", fake_forward)

    response = client.get("/api/sessions")
    assert response.status_code == 502


def test_get_session_messages_converts_format(monkeypatch):
    """会话消息：转发 + 转换层还原前端格式。"""
    async def fake_forward(method, path):
        assert path == "/api/sessions/sid-aaa/messages"
        return _hermes_response(200, {
            "object": "list",
            "data": [
                {"role": "user", "content": "一个人"},
                {"role": "assistant", "content": "好的"},
            ],
        })

    monkeypatch.setattr(sessions, "forward_to_hermes", fake_forward)

    response = client.get("/api/sessions/sid-aaa/messages")

    assert response.status_code == 200
    assert response.json()["data"] == [
        {"role": "user", "content": "一个人"},
        {"role": "agent", "content": "好的"},
    ]


def test_delete_session_idempotent_on_404(monkeypatch):
    """删除：404（已不存在）也视为成功（幂等）。"""
    async def fake_forward(method, path):
        assert method == "DELETE"
        return _hermes_response(404, {"error": "not found"})

    monkeypatch.setattr(sessions, "forward_to_hermes", fake_forward)

    response = client.delete("/api/sessions/sid-aaa")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_open_finder_opens_existing_folder(monkeypatch, tmp_path):
    """打开 Finder：调用 open 命令。"""
    output_root = tmp_path / "output"
    folder = output_root / "20260814_075856"
    folder.mkdir(parents=True)

    opened = []
    monkeypatch.setattr(sessions.subprocess, "run", lambda cmd, timeout: opened.append(cmd))

    response = client.post("/api/open-finder", json={"folder_name": "20260814_075856"})

    assert response.status_code == 200
    assert opened == [["open", str(folder)]]


def test_open_finder_rejects_missing_folder(monkeypatch):
    """打开 Finder：文件夹不存在返回 404。"""
    response = client.post("/api/open-finder", json={"folder_name": "20260814_999999"})
    assert response.status_code == 404


def test_open_finder_rejects_illegal_name(monkeypatch):
    """打开 Finder：非法文件夹名（路径穿越）返回 400。"""
    response = client.post("/api/open-finder", json={"folder_name": "../../etc"})
    assert response.status_code == 400
