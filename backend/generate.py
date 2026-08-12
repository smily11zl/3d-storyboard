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
GENERATION_TIMEOUT_SECONDS = int(os.environ.get("GENERATION_TIMEOUT_SECONDS", "600"))


def get_output_root() -> Path:
    """输出根目录（动态计算，便于测试替换 GENERATE_ROOT）。"""
    return GENERATE_ROOT / "output"
GENERATION_INSTRUCTION_PREFIX = (
    "请使用 storyboard-scene-generator skill 生成 3D 场景。"
    "输出目录已指定，请将最终 .blend 保存为: {output_dir}/scene.blend。"
    "所有中间文件放在该目录内。用户需求: {description}"
)

router = APIRouter(prefix="/api/generate", tags=["generate"])

# task_id → {"description", "output_dir", "queue", "cancel_event", "started"}
ACTIVE_TASKS: dict[str, dict] = {}


class GeneratePayload(BaseModel):
    description: str


# ── 可替换依赖（测试 mock 点）──────────────────────────────────────────────

async def stream_from_agent(description: str, output_dir: Path):
    """向 Hermes API Server 提交生成，产出事件流。

    yield: {"type": "text"|"tool"|"done", "content": str}
    真实实现：POST /v1/responses (SSE)，解析 message.delta / tool.* 事件。
    """
    import httpx

    model = settings_module.read_current_settings()["model"]
    instruction = GENERATION_INSTRUCTION_PREFIX.format(
        output_dir=output_dir, description=description
    )
    api_key = agent_service.get_api_server_key()
    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": instruction},
            {"role": "user", "content": description},
        ],
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=None) as http_client:
        async with http_client.stream(
            "POST",
            f"{agent_service.AGENT_BASE_URL}/v1/responses",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
        ) as response:
            if response.status_code != 200:
                raise RuntimeError(f"Agent 返回错误 {response.status_code}")
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue
                event_type = event.get("type", "")
                if event_type == "response.output_text.delta":
                    yield {"type": "text", "content": event.get("delta", "")}
                elif event_type in ("tool.start", "tool.progress", "tool.complete"):
                    yield {"type": "tool", "content": json.dumps(event, ensure_ascii=False)}
                elif event_type == "error" or event.get("finish_reason") == "error":
                    error_message = event.get("error", {}).get("message", "未知错误")
                    raise RuntimeError(f"Agent 生成失败: {error_message}")
                elif event_type == "response.failed":
                    error_message = (
                        event.get("response", {}).get("error", {}).get("message")
                        or event.get("error", {}).get("message")
                        or event.get("error", {}).get("code")
                        or "Agent 生成失败（未知原因）"
                    )
                    raise RuntimeError(f"Agent 生成失败: {error_message}")
                elif event_type in ("response.completed", "message.complete"):
                    yield {"type": "done", "content": "生成完成"}
                    break


async def export_scene(blend_path: Path, output_dir: Path) -> dict:
    """导出 .blend → glTF（复用上传流程：hash → exports/<hash> → 元数据）。

    返回 shot 元数据（export_hash / gltf_output_url / cameras / animations…）。
    """
    from backend import main as main_module  # 延迟导入避免循环依赖

    try:
        export_hash = main_module.compute_file_hash(str(blend_path))
        export_directory = main_module.EXPORTS_ROOT / export_hash
        export_directory.mkdir(parents=True, exist_ok=True)
        await main_module.run_export(str(blend_path), str(export_directory))

        gltf_filepath = export_directory / main_module.GLTF_OUTPUT_NAME
        if not gltf_filepath.is_file():
            raise RuntimeError("Export completed but scene.gltf was not created")

        metadata = main_module.parse_gltf_for_metadata(str(gltf_filepath))
        metadata["export_hash"] = export_hash
        metadata["gltf_output_url"] = (
            f"/static/exports/{export_hash}/{main_module.GLTF_OUTPUT_NAME}"
        )
        main_module.save_shot_metadata(export_hash, metadata)
        main_module.enforce_disk_quota()
        return metadata
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
    output_dir: Path, status: str, error: str | None = None, shot: dict | None = None
) -> None:
    status_data = {"status": status}
    if error:
        status_data["error"] = error
    if shot:
        status_data["shot"] = shot
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
            async for event in stream_from_agent(record["description"], output_dir):
                if record["cancel_event"].is_set():
                    break
                log_parts.append(f"[{event['type']}] {event['content']}")
                await record["queue"].put(event)
                if event["type"] == "done":
                    break

        if record["cancel_event"].is_set():
            write_status(output_dir, "cancelled")
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

        write_status(output_dir, "done", shot=shot_metadata)
        record["final_status"] = "done"
        log_parts.append("[done] 导出完成")
    except TimeoutError:
        write_status(output_dir, "failed", error="生成超时（超过 10 分钟），已终止")
        record["final_status"] = "failed"
        kill_blender_processes(output_dir)
        log_parts.append("[timeout] 生成超时，已清理残留进程")
    except Exception as error:
        write_status(output_dir, "failed", error=str(error))
        record["final_status"] = "failed"
        log_parts.append(f"[failed] {error}")
    finally:
        write_generation_log(output_dir, "\n".join(log_parts))
        await record["queue"].put(
            {"type": "status", "content": record.get("final_status", "finished")}
        )
        ACTIVE_TASKS.pop(task_id, None)


# ── HTTP 端点 ──────────────────────────────────────────────────────────────

@router.post("")
def create_generation(payload: GeneratePayload) -> dict:
    """创建生成任务（不立即启动；SSE 连接时启动）。"""
    if ACTIVE_TASKS:
        raise HTTPException(status_code=409, detail="已有生成任务进行中，请等待完成")
    if not payload.description.strip():
        raise HTTPException(status_code=422, detail="描述不能为空")

    task_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = get_output_root() / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    write_status(output_dir, "running")
    ACTIVE_TASKS[task_id] = {
        "description": payload.description.strip(),
        "output_dir": output_dir,
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
