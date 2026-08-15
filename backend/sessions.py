"""V3 多会话历史 — 转发 Hermes /api/sessions + 消息转换层 + 打开 Finder。

复用 Hermes 内嵌 API Server 的会话存储（state.db），不自建历史存储。
session_id ↔ 输出文件夹名的映射通过 status.json 的 session_id 字段（阶段 2 写入）。
"""
import json
import subprocess
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend import agent_service

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GENERATE_OUTPUT_ROOT = PROJECT_ROOT / "generate" / "output"

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
open_finder_router = APIRouter(prefix="/api", tags=["sessions"])


class OpenFinderPayload(BaseModel):
    folder_name: str


# ── 可替换依赖（测试 mock 点）──────────────────────────────────────────────

async def forward_to_hermes(method: str, path: str) -> httpx.Response:
    """转发请求到 Hermes API Server（带内部 API key 鉴权）。"""
    api_key = agent_service.get_api_server_key()
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=30) as client:
        return await client.request(
            method, f"{agent_service.AGENT_BASE_URL}{path}", headers=headers
        )


# ── 消息转换层 ─────────────────────────────────────────────────────────────

def convert_hermes_messages(hermes_messages: list[dict]) -> list[dict]:
    """Hermes 底层消息（user/assistant/tool）→ 前端 UI 消息格式。

    - user content              → user
    - assistant content 非空     → agent 文本
    - assistant tool_calls      → tool_start（拆 tool_calls 数组）
    - tool content + tool_name  → tool_output（截断）

    tool_end 耗时 Hermes 未存，历史回放中省略。
    """
    result = []
    for message in hermes_messages:
        role = message.get("role")
        if role == "user":
            result.append({"role": "user", "content": message.get("content") or ""})
        elif role == "assistant":
            reasoning = message.get("reasoning") or message.get("reasoning_content")
            if reasoning:
                result.append({"role": "reasoning", "content": reasoning})
            content = message.get("content") or ""
            if content:
                result.append({"role": "agent", "content": content})
            tool_calls = message.get("tool_calls") or []
            if isinstance(tool_calls, str):
                try:
                    tool_calls = json.loads(tool_calls)
                except json.JSONDecodeError:
                    tool_calls = []
            for call in tool_calls:
                function = call.get("function", call) if isinstance(call, dict) else {}
                result.append(
                    {
                        "role": "tool_start",
                        "name": function.get("name", "tool"),
                        "content": (function.get("arguments") or "")[:120],
                    }
                )
        elif role == "tool":
            result.append(
                {"role": "tool_output", "content": (message.get("content") or "")[:150]}
            )
    return result


# ── session_id ↔ 文件夹名映射 ──────────────────────────────────────────────

def find_folder_for_session(session_id: str) -> str | None:
    """通过 status.json 的 session_id 字段精确反查输出文件夹名。"""
    if not GENERATE_OUTPUT_ROOT.exists():
        return None
    for folder in sorted(GENERATE_OUTPUT_ROOT.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        status_file = folder / "status.json"
        if not status_file.is_file():
            continue
        try:
            status = json.loads(status_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if status.get("session_id") == session_id:
            return folder.name
    return None


def folder_from_timestamp(started_at: float) -> str:
    """session.started_at（epoch 秒）→ YYYYMMDD_HHMMSS 兜底显示名。"""
    try:
        return datetime.fromtimestamp(float(started_at)).strftime("%Y%m%d_%H%M%S")
    except (TypeError, ValueError, OSError):
        return ""


def find_folder_near_timestamp(started_at: float) -> str | None:
    """按时间戳 ±3 秒容差匹配真实文件夹名（旧数据无 session_id 映射时兜底）。"""
    if not GENERATE_OUTPUT_ROOT.exists():
        return None
    target = float(started_at)
    best_name = None
    best_diff = float("inf")
    for folder in GENERATE_OUTPUT_ROOT.iterdir():
        if not folder.is_dir():
            continue
        try:
            folder_time = datetime.strptime(folder.name, "%Y%m%d_%H%M%S").timestamp()
        except ValueError:
            continue
        diff = abs(folder_time - target)
        if diff < best_diff:
            best_diff = diff
            best_name = folder.name
    return best_name if best_diff <= 3 else None


# ── HTTP 端点 ──────────────────────────────────────────────────────────────

@open_finder_router.post("/open-finder")
def open_finder(payload: OpenFinderPayload) -> dict:
    """在 Finder 中打开输出文件夹（macOS open 命令）。"""
    folder_name = payload.folder_name
    # 安全校验：仅允许时间戳格式（YYYYMMDD_HHMMSS），防路径穿越
    if not folder_name.replace("_", "").isdigit():
        raise HTTPException(status_code=400, detail="非法文件夹名")
    folder_path = (GENERATE_OUTPUT_ROOT / folder_name).resolve()
    if GENERATE_OUTPUT_ROOT.resolve() not in folder_path.parents:
        raise HTTPException(status_code=400, detail="非法路径")
    if not folder_path.is_dir():
        raise HTTPException(status_code=404, detail="输出文件夹不存在")
    try:
        subprocess.run(["open", str(folder_path)], timeout=5)
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"打开 Finder 失败: {error}")
    return {"ok": True, "path": str(folder_path)}


@router.get("")
async def list_sessions() -> dict:
    """历史列表：转发 Hermes 会话列表，附加文件夹名/预览/输出存在性。"""
    try:
        response = await forward_to_hermes("GET", "/api/sessions")
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Hermes 不可用: {error}")
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Hermes 会话列表获取失败")

    body = response.json()
    result = []
    for session in body.get("data", []):
        # 只显示项目生成任务产生的会话（source=api_server）
        if session.get("source") != "api_server":
            continue
        session_id = session.get("id", "")
        folder_name = (
            find_folder_for_session(session_id)
            or find_folder_near_timestamp(session.get("started_at", 0))
            or folder_from_timestamp(session.get("started_at", 0))
        )
        result.append(
            {
                "id": session_id,
                "folder_name": folder_name,
                "preview": session.get("preview") or "",
                "input_tokens": session.get("input_tokens", 0),
                "output_tokens": session.get("output_tokens", 0),
                "estimated_cost_usd": session.get("estimated_cost_usd"),
                "message_count": session.get("message_count", 0),
                "has_output": (GENERATE_OUTPUT_ROOT / folder_name).is_dir()
                if folder_name
                else False,
                "started_at": session.get("started_at"),
            }
        )
    result.sort(key=lambda item: item.get("started_at") or 0, reverse=True)
    return {"object": "list", "data": result}


@router.get("/{session_id}/messages")
async def get_session_messages(session_id: str) -> dict:
    """会话聊天记录：转发 Hermes messages，经转换层还原前端格式。"""
    try:
        response = await forward_to_hermes("GET", f"/api/sessions/{session_id}/messages")
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Hermes 不可用: {error}")
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Hermes 会话消息获取失败")
    body = response.json()
    converted = convert_hermes_messages(body.get("data", []))
    return {"object": "list", "session_id": session_id, "data": converted}


@router.delete("/{session_id}")
async def delete_session(session_id: str) -> dict:
    """删除会话（仅删 Hermes session 记录，输出文件夹保留）。"""
    try:
        response = await forward_to_hermes("DELETE", f"/api/sessions/{session_id}")
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Hermes 不可用: {error}")
    # 幂等：404（已不存在）也视为成功
    if response.status_code not in (200, 204, 404):
        raise HTTPException(status_code=502, detail="Hermes 会话删除失败")
    return {"ok": True, "session_id": session_id}
