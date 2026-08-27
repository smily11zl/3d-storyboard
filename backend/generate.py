"""V2 生成任务 — 提交/SSE 流式/完成衔接/失败/取消/超时。

任务生命周期（status.json）:
  running → done | failed | cancelled
"""
import asyncio
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend import agent_service, settings as settings_module

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GENERATE_ROOT = Path(os.environ.get("GENERATE_ROOT", PROJECT_ROOT / "generate"))
GENERATION_TIMEOUT_SECONDS = int(os.environ.get("GENERATION_TIMEOUT_SECONDS", "1200"))


def get_output_root() -> Path:
    """输出根目录（动态计算，便于测试替换 GENERATE_ROOT）。"""
    return GENERATE_ROOT / "output"


def get_upload_output_root() -> Path:
    """上传源的输出根目录（generate/upload_output，与 output 并列）。"""
    return GENERATE_ROOT / "upload_output"


def get_latest_blend(folder: Path) -> Path | None:
    """返回 folder 里 mtime 最新的 .blend 文件（排除 .blend1 备份），无则 None。"""
    blends = [p for p in folder.iterdir() if p.is_file() and p.suffix == ".blend"]
    if not blends:
        return None
    return max(blends, key=lambda p: p.stat().st_mtime)


GENERATION_INSTRUCTION_PREFIX = (
    "请使用 storyboard-scene-generator skill 生成 3D 场景。"
    "输出目录已指定，请将最终 .blend 保存为: {output_dir}/scene.blend。"
    "所有中间文件放在该目录内。"
)

EDIT_INSTRUCTION_PREFIX = (
    "这是对已有场景的二次修改。请读回 {output_dir}/script.py，"
    "按用户要求修改代码，重新运行生成 scene.blend 覆盖。不要新建代码文件。"
)


def build_instruction(output_dir: Path, is_edit: bool) -> str:
    """生成指令（system prompt）：首轮生成 / 二次修改两种模式。"""
    template = EDIT_INSTRUCTION_PREFIX if is_edit else GENERATION_INSTRUCTION_PREFIX
    return template.format(output_dir=output_dir)

router = APIRouter(prefix="/api/generate", tags=["generate"])

# task_id → {"description", "output_dir", "queue", "cancel_event", "started"}
ACTIVE_TASKS: dict[str, dict] = {}


class GeneratePayload(BaseModel):
    description: str
    session_id: str | None = None  # 二次修改时传入，续接已有会话
    folder_name: str | None = None  # 二次修改时传入，定位输出文件夹（旧会话无 session_id 映射时兜底）


# ── 可替换依赖（测试 mock 点）──────────────────────────────────────────────

async def stream_from_agent(description: str, output_dir: Path, session_id: str | None = None):
    """向 Hermes API Server 提交生成，产出事件流。

    首轮（session_id=None）：先 POST /api/sessions 建会话拿 session_id，
    再走 /api/sessions/{id}/chat/stream 续接生成。
    二次修改（session_id 有值）：直接续接已有会话。

    yield: session_created / text / tool_start / tool_end / tool_output / done
    真实实现走 Hermes 的 session chat 流式端点（SSE: event: + data: 格式）。
    """
    import httpx

    api_key = agent_service.get_api_server_key()
    headers = {"Authorization": f"Bearer {api_key}"}
    is_edit = session_id is not None
    instruction = build_instruction(output_dir, is_edit)

    async with httpx.AsyncClient(timeout=None) as http_client:
        # 首轮：建会话拿 session_id（可控，用于写 status.json 映射）
        if session_id is None:
            create_response = await http_client.post(
                f"{agent_service.AGENT_BASE_URL}/api/sessions",
                json={},
                headers=headers,
            )
            if create_response.status_code not in (200, 201):
                raise RuntimeError(f"创建会话失败 {create_response.status_code}")
            session_id = create_response.json()["session"]["id"]
            yield {"type": "session_created", "session_id": session_id}

        async with http_client.stream(
            "POST",
            f"{agent_service.AGENT_BASE_URL}/api/sessions/{session_id}/chat/stream",
            json={"message": description, "instructions": instruction},
            headers=headers,
        ) as response:
            if response.status_code != 200:
                raise RuntimeError(f"续接生成失败 {response.status_code}")

            event_name = None
            async for line in response.aiter_lines():
                if line.startswith("event: "):
                    event_name = line[7:].strip()
                elif line.startswith("data: "):
                    try:
                        event = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue
                    if event_name == "assistant.delta":
                        delta = event.get("delta", "")
                        if delta:
                            yield {"type": "text", "content": delta}
                    elif event_name == "tool.started":
                        arguments = event.get("args") or {}
                        if not isinstance(arguments, str):
                            arguments = json.dumps(arguments, ensure_ascii=False)
                        yield {
                            "type": "tool_start",
                            "name": event.get("tool_name", "tool"),
                            "arguments": arguments,
                        }
                    elif event_name == "tool.completed":
                        yield {
                            "type": "tool_end",
                            "name": event.get("tool_name", "tool"),
                            "status": "completed",
                        }
                        preview = event.get("preview")
                        if preview:
                            if not isinstance(preview, str):
                                preview = json.dumps(preview, ensure_ascii=False)
                            yield {"type": "tool_output", "content": preview[:500]}
                    elif event_name == "tool.failed":
                        yield {
                            "type": "tool_end",
                            "name": event.get("tool_name", "tool"),
                            "status": "failed",
                        }
                    elif event_name == "run.completed":
                        usage = event.get("usage") or {}
                        yield {
                            "type": "done",
                            "content": "生成完成",
                            "usage": {
                                "input_tokens": usage.get("input_tokens", 0),
                                "output_tokens": usage.get("output_tokens", 0),
                                "total_tokens": usage.get("total_tokens", 0),
                            },
                        }
                    elif event_name == "error":
                        raise RuntimeError(f"Agent 生成失败: {event.get('message', '未知')}")
                    elif event_name == "done":
                        break


async def export_scene(blend_path: Path, output_dir: Path) -> dict:
    """导出 .blend → glTF（复用主流程 ingest_blend：hash → exports/<hash> → 元数据）。

    返回 shot 元数据（export_hash / gltf_output_url / cameras / animations…）。
    output_dir 参数保留以兼容调用方与测试 mock；实际入库逻辑统一走 ingest_blend。
    """
    from backend import main as main_module  # 延迟导入避免循环依赖

    try:
        return await main_module.ingest_blend(
            str(blend_path),
            source={"type": "chat", "folder": output_dir.name},
        )
    except RuntimeError as error:
        raise RuntimeError(f"导出失败: {error}") from error


def kill_blender_processes(output_dir: Path) -> None:
    """杀掉命令行中包含该输出目录的 blender 进程（残留清理）。"""
    try:
        output = subprocess.run(
            ["ps", "ax", "-o", "pid=,command="],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
        for line in output.splitlines():
            if "blender" in line and str(output_dir) in line:
                pid = line.split()[0]
                subprocess.run(["kill", "-9", pid], timeout=5)
    except Exception:
        pass


# ── 状态读写 ───────────────────────────────────────────────────────────────

def write_status(
    output_dir: Path,
    status: str,
    error: str | None = None,
    shot: dict | None = None,
    usage: dict | None = None,
    session_id: str | None = None,
) -> None:
    status_data: dict = {"status": status}
    if error:
        status_data["error"] = error
    if shot:
        status_data["shot"] = shot
    if usage:
        status_data["usage"] = usage
    if session_id:
        status_data["session_id"] = session_id
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "status.json").write_text(
        json.dumps(status_data, ensure_ascii=False), encoding="utf-8"
    )


def write_generation_log(output_dir: Path, content: str) -> None:
    (output_dir / "generation.log").write_text(content, encoding="utf-8")


# ── 任务执行 ───────────────────────────────────────────────────────────────

async def run_generation_task(task_id: str) -> None:
    """执行生成任务：流式消费 agent 事件 → 导出 → 状态落盘。"""
    record = ACTIVE_TASKS[task_id]
    output_dir = record["output_dir"]
    log_parts = []
    try:
        async with asyncio.timeout(GENERATION_TIMEOUT_SECONDS):
            async for event in stream_from_agent(
                record["description"], output_dir, record.get("session_id")
            ):
                if record["cancel_event"].is_set():
                    break
                if event["type"] == "session_created":
                    # 首轮建会话：记录 session_id 并写回 status.json（映射）
                    record["session_id"] = event["session_id"]
                    write_status(output_dir, "running", session_id=event["session_id"])
                log_parts.append(
                    f"[{event['type']}] {event.get('content', json.dumps({k: v for k, v in event.items() if k != 'type'}, ensure_ascii=False)[:200])}"
                )
                if event["type"] == "done" and event.get("usage"):
                    record["usage"] = event["usage"]
                await record["queue"].put(event)
                if event["type"] == "done":
                    break

        if record["cancel_event"].is_set():
            write_status(output_dir, "cancelled", session_id=record.get("session_id"))
            record["final_status"] = "cancelled"
            return

        blend_path = output_dir / "scene.blend"
        if not blend_path.exists():
            raise RuntimeError(f"生成完成但未找到 {blend_path}")

        # 导出（自动重试 1 次）→ 返回 shot 元数据（gltf URL / cameras / animations）
        last_error = None
        shot_metadata = None
        for attempt in (1, 2):
            try:
                shot_metadata = await export_scene(blend_path, output_dir)
                last_error = None
                break
            except Exception as error:
                last_error = error
                log_parts.append(f"[export] 第 {attempt} 次导出失败: {error}")
        if last_error:
            raise RuntimeError(f"导出失败（已重试）: {last_error}")

        write_status(
            output_dir,
            "done",
            shot=shot_metadata,
            usage=record.get("usage"),
            session_id=record.get("session_id"),
        )
        record["final_status"] = "done"
        log_parts.append("[done] 导出完成")
    except TimeoutError:
        write_status(
            output_dir,
            "failed",
            error=f"生成超时（超过 {GENERATION_TIMEOUT_SECONDS // 60} 分钟），已终止",
            session_id=record.get("session_id"),
        )
        record["final_status"] = "failed"
        kill_blender_processes(output_dir)
        log_parts.append("[timeout] 生成超时，已清理残留进程")
    except Exception as error:
        write_status(
            output_dir,
            "failed",
            error=str(error),
            session_id=record.get("session_id"),
        )
        record["final_status"] = "failed"
        log_parts.append(f"[failed] {error}")
    finally:
        write_generation_log(output_dir, "\n".join(log_parts))
        await record["queue"].put(
            {
                "type": "status",
                "content": record.get("final_status", "finished"),
                "usage": record.get("usage"),
            }
        )
        ACTIVE_TASKS.pop(task_id, None)


# ── HTTP 端点 ──────────────────────────────────────────────────────────────

@router.post("")
def create_generation(payload: GeneratePayload) -> dict:
    """创建生成任务（不立即启动；SSE 连接时启动）。

    首轮（session_id=None）：新建时间戳文件夹。
    二次修改（session_id 有值）：复用该会话对应的输出文件夹。
    """
    if ACTIVE_TASKS:
        raise HTTPException(status_code=409, detail="已有生成任务进行中，请等待完成")
    if not payload.description.strip():
        raise HTTPException(status_code=422, detail="描述不能为空")

    session_id = payload.session_id
    if session_id:
        # 二次修改：优先用前端传来的 folder_name，否则按 session_id 反查
        folder_name = payload.folder_name
        if not folder_name:
            from backend import sessions as sessions_module

            folder_name = sessions_module.find_folder_for_session(session_id)
        if not folder_name:
            raise HTTPException(status_code=404, detail="会话对应的输出文件夹不存在")
        output_dir = get_output_root() / folder_name
        if not output_dir.is_dir():
            raise HTTPException(status_code=404, detail="会话对应的输出文件夹不存在")
        task_id = folder_name
    else:
        # 首轮：新建时间戳文件夹
        task_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = get_output_root() / task_id
        output_dir.mkdir(parents=True, exist_ok=True)

    write_status(output_dir, "running")
    ACTIVE_TASKS[task_id] = {
        "description": payload.description.strip(),
        "output_dir": output_dir,
        "session_id": session_id,
        "queue": asyncio.Queue(),
        "cancel_event": asyncio.Event(),
        "started": False,
    }
    return {"task_id": task_id, "status": "running", "output_dir": str(output_dir)}


@router.get("/{task_id}")
def get_generation_status(task_id: str) -> dict:
    """查询任务状态（status.json 内容，任务完成后也可查）。"""
    status_file = get_output_root() / task_id / "status.json"
    if not status_file.exists():
        raise HTTPException(status_code=404, detail="任务不存在")
    return json.loads(status_file.read_text(encoding="utf-8"))


@router.post("/{task_id}/reload")
async def reload_shot(task_id: str) -> dict:
    """重新转化会话文件夹里的 scene.blend（相当于自动重新上传一次）。

    切换聊天时调用：从源 blend 重新派生最新 shot，而不是用旧的缓存 shot。
    保留 status.json 里的 session_id / usage，只更新 shot。
    """
    output_dir = get_output_root() / task_id
    blend_path = get_latest_blend(output_dir)
    if blend_path is None:
        raise HTTPException(status_code=404, detail="blend 不存在")

    # 读旧 status.json，保留 session_id / usage（若有）
    status_file = output_dir / "status.json"
    previous_status: dict = {}
    if status_file.exists():
        try:
            previous_status = json.loads(status_file.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            previous_status = {}

    shot_metadata = await export_scene(blend_path, output_dir)

    write_status(
        output_dir,
        "done",
        shot=shot_metadata,
        usage=previous_status.get("usage"),
        session_id=previous_status.get("session_id"),
    )
    return shot_metadata


@router.get("/{task_id}/stream")
async def stream_generation(task_id: str):
    """SSE 流式转发生成过程；首次连接时启动任务；断开即中断。"""
    record = ACTIVE_TASKS.get(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="任务不存在")

    if not record["started"]:
        record["started"] = True
        asyncio.create_task(run_generation_task(task_id))

    async def event_generator():
        try:
            while True:
                event = await record["queue"].get()
                if event.get("type") == "status":
                    break
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            # 客户端断开：任务继续运行（不取消）——取消只走显式 stop 端点。
            # 浏览器 EventSource 会自动重连并继续接收剩余事件；
            # 若任务已结束，重连后 status 事件已消费，前端可查询状态端点收尾。
            pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{task_id}/stop")
def stop_generation(task_id: str) -> dict:
    """取消生成：中断 agent + 清理残留 blender 进程 + 状态落盘。"""
    record = ACTIVE_TASKS.get(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="任务不存在")

    record["cancel_event"].set()
    kill_blender_processes(record["output_dir"])
    write_status(record["output_dir"], "cancelled")
    ACTIVE_TASKS.pop(task_id, None)
    return {"ok": True, "message": "已取消生成"}
