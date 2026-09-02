"""FastAPI application for Shot Viewer — .blend upload, glTF export, and static serving."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.settings import router as settings_router
from backend.generate import router as generate_router, get_upload_output_root, get_latest_blend, get_output_root
from backend.sessions import router as sessions_router
from backend.sessions import open_finder_router
from backend.shot_segments import parse_segments_sidecar
from backend.edit_operations import parse_full_edit
from backend.export_video_service import compose_single

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPORT_SCRIPT = PROJECT_ROOT / "backend" / "export_shot.py"
APPLY_EDIT_SCRIPT = PROJECT_ROOT / "backend" / "apply_edit.py"
EXPORT_VIDEO_SCRIPT = PROJECT_ROOT / "backend" / "export_video.py"

# Configurable with defaults
EXPORTS_ROOT = Path(os.environ.get("EXPORTS_ROOT", PROJECT_ROOT / "exports"))
MAX_DISK_MB = int(os.environ.get("MAX_DISK_MB", "500"))
MAX_DISK_BYTES = MAX_DISK_MB * 1024 * 1024
CACHE_FILE = "shot_metadata.json"
GLTF_OUTPUT_NAME = "scene.gltf"

EXPORTS_ROOT.mkdir(parents=True, exist_ok=True)

application = FastAPI(title="Storyboard Shot Viewer")

application.include_router(settings_router)
application.include_router(generate_router)
application.include_router(sessions_router)
application.include_router(open_finder_router)

application.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def compute_file_hash(filepath: str) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _resolve_upload_blend(source: dict | None) -> Path | None:
    """upload 源：source.file → upload_output/<file>（扁平单文件）。"""
    if not source or source.get("type") != "upload":
        return None
    filename = source.get("file")
    if not filename:
        return None
    return get_upload_output_root() / filename


def _resolve_chat_folder(source: dict | None) -> Path | None:
    """chat 源：source.folder → output/<folder>（版本化目录）。"""
    if not source or source.get("type") != "chat":
        return None
    folder_name = source.get("folder")
    if not folder_name:
        return None
    return get_output_root() / folder_name


def enforce_disk_quota():
    """Remove oldest export directories until total size is under MAX_DISK_BYTES."""
    if not EXPORTS_ROOT.exists():
        return

    entries = []
    for entry in EXPORTS_ROOT.iterdir():
        if entry.is_dir():
            total_entry_size = sum(
                filepath.stat().st_size
                for filepath in entry.rglob("*")
                if filepath.is_file()
            )
            entries.append((entry.stat().st_mtime, total_entry_size, entry))

    entries.sort()  # Oldest first
    total_disk_used = sum(item[1] for item in entries)

    while total_disk_used > MAX_DISK_BYTES and entries:
        _, entry_size, entry_path = entries.pop(0)
        import shutil
        shutil.rmtree(entry_path, ignore_errors=True)
        total_disk_used -= entry_size


def parse_gltf_for_metadata(gltf_filepath: str) -> dict:
    """Extract camera names, animation names, and scene info from glTF JSON."""
    with open(gltf_filepath) as file_handle:
        gltf_data = json.load(file_handle)

    camera_list = []
    if "cameras" in gltf_data:
        for node in gltf_data.get("nodes", []):
            if "camera" in node:
                camera_index = node["camera"]
                # 用节点名（= Blender object 名，如 cam_01_front），
                # 不是相机数据块名（默认"摄像机"）——前端按名字在场景中查找节点
                camera_name = node.get("name", f"camera_{camera_index}")
                camera_list.append({"camera_name": camera_name})

    animation_list = []
    for animation in gltf_data.get("animations", []):
        animation_name = animation.get("name", "unnamed_animation")
        # Find the max time across all channels and samplers for duration
        max_time = 0.0
        for channel in animation.get("channels", []):
            sampler_index = channel.get("sampler")
            if sampler_index is not None:
                sampler = animation.get("samplers", [])[sampler_index]
                input_accessor_index = sampler.get("input")
                if input_accessor_index is not None:
                    accessor = gltf_data.get("accessors", [])[input_accessor_index]
                    max_times = accessor.get("max", [0])
                    if max_times:
                        max_time = max(max_time, max(max_times))
        animation_list.append({
            "animation_name": animation_name,
            "animation_length_seconds": round(max_time, 3),
        })

    # Compute overall duration from animations
    overall_duration = max(
        (anim["animation_length_seconds"] for anim in animation_list),
        default=0.0,
    )

    return {
        "cameras": camera_list,
        "animations": animation_list,
        "duration_seconds": round(overall_duration, 3),
        "frames_per_second": 24,  # glTF doesn't store FPS; default assumption
    }


def read_frame_aspect(export_directory: str) -> float | None:
    """Read the camera frame aspect written by export_shot.py (sidecar).
    Returns None if absent (older exports)."""
    aspect_filepath = os.path.join(export_directory, "frame_aspect.txt")
    if not os.path.isfile(aspect_filepath):
        return None
    try:
        with open(aspect_filepath) as file_handle:
            return float(file_handle.read().strip())
    except (ValueError, OSError):
        return None


def read_segments_sidecar(export_directory: str) -> dict | None:
    """Read the segments.json sidecar written by export_shot.py.
    Returns None if absent (older exports)."""
    segments_filepath = os.path.join(export_directory, "segments.json")
    if not os.path.isfile(segments_filepath):
        return None
    try:
        with open(segments_filepath) as file_handle:
            return json.load(file_handle)
    except (ValueError, OSError):
        return None


async def run_export(input_filepath: str, output_directory: str) -> bool:
    """Run Blender export as an async subprocess."""
    command = [
        "blender", "--background",
        "--python", str(EXPORT_SCRIPT),
        "--",
        input_filepath, output_directory,
    ]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await process.communicate()
    success = process.returncode == 0

    # Print Blender export output to terminal
    stdout_text = stdout_bytes.decode()
    if stdout_text.strip():
        print(stdout_text.strip(), flush=True)

    if not success:
        error_message = stderr_bytes.decode() or stdout_text or "Unknown error"
        raise RuntimeError(f"Blender export failed: {error_message[:500]}")

    return True


async def run_apply_edit(input_blend: str, operations_file: str, output_blend: str) -> bool:
    """Run Blender apply_edit.py as an async subprocess."""
    command = [
        "blender", "--background",
        "--python", str(APPLY_EDIT_SCRIPT),
        "--",
        input_blend, operations_file, output_blend,
    ]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await process.communicate()
    if process.returncode != 0:
        error_message = stderr_bytes.decode() or stdout_bytes.decode() or "Unknown error"
        raise RuntimeError(f"Blender edit failed: {error_message[:500]}")
    return True


CHUNK_FRAMES = 50  # 每块最多渲染 50 帧，随后重启 Blender 进程，避免单进程长渲染累积卡死


async def run_export_video(description_file: str, task: ExportTask | None = None) -> bool:
    """分块渲染 PNG（每块重启 Blender 进程）+ 逐个合成 MP4。"""
    with open(description_file) as file_handle:
        desc = json.load(file_handle)
    blend = desc["blend"]
    output_dir = desc["output_dir"]
    segments = desc["segments"]
    resolution = desc.get("resolution", "1080p")
    fps = desc.get("fps", 24)

    # 构建任务列表（每个有段相机：1 整段 + N 段）
    cameras: dict[str, list] = {}
    for segment in segments:
        cameras.setdefault(segment["camera_name"], []).append(segment)
    task_specs = []
    for camera_name, camera_segments in cameras.items():
        min_start = min(seg["start_time"] for seg in camera_segments)
        max_end = max(seg["end_time"] for seg in camera_segments)
        task_specs.append(
            {
                "task_name": f"{camera_name}_full",
                "camera_name": camera_name,
                "frame_start": int(min_start * fps),
                "frame_end": int(max_end * fps),
            }
        )
        for segment in camera_segments:
            task_specs.append(
                {
                    "task_name": f"{camera_name}_{segment['segment_name']}",
                    "camera_name": camera_name,
                    "frame_start": int(segment["start_time"] * fps),
                    "frame_end": int(segment["end_time"] * fps),
                }
            )

    # 写 manifest（任务元信息），主进程据此逐个合成
    manifest_tasks = []
    for spec in task_specs:
        frames_dir = os.path.join(output_dir, "frames", spec["task_name"])
        manifest_tasks.append(
            {
                "name": spec["task_name"],
                "frames_dir": frames_dir,
                "frame_start": spec["frame_start"],
                "frame_count": spec["frame_end"] - spec["frame_start"] + 1,
            }
        )
    with open(os.path.join(output_dir, "manifest.json"), "w") as file_handle:
        json.dump({"fps": fps, "tasks": manifest_tasks}, file_handle)

    # 构建块列表（每个任务按 CHUNK_FRAMES 分块）
    chunks = []
    for spec in task_specs:
        frames_dir = os.path.join(output_dir, "frames", spec["task_name"])
        for chunk_start in range(spec["frame_start"], spec["frame_end"] + 1, CHUNK_FRAMES):
            chunk_end = min(chunk_start + CHUNK_FRAMES - 1, spec["frame_end"])
            chunks.append(
                {
                    "task_name": spec["task_name"],
                    "camera_name": spec["camera_name"],
                    "frame_start": chunk_start,
                    "frame_end": chunk_end,
                    "frames_dir": frames_dir,
                    "task_frame_start": spec["frame_start"],
                }
            )

    composed: set[str] = set()
    for chunk in chunks:
        if task is not None and task.cancel_requested:
            task.status = "cancelled"
            task.error = "Export cancelled by user"
            break
        if task is not None:
            # 渲染前：显示上一块完成的帧数
            _write_task_progress(task, chunk, after_render=False)
        chunk_desc = {
            "blend": blend,
            "output_dir": output_dir,
            "resolution": resolution,
            "chunk": chunk,
        }
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as temp_file:
            json.dump(chunk_desc, temp_file)
            chunk_file = temp_file.name
        try:
            await _run_blender_chunk(chunk_file, task)
        finally:
            try:
                os.unlink(chunk_file)
            except OSError:
                pass
        if task is not None:
            # 渲染后：显示本块完成的帧数（文件内进度以块为单位跳变）
            _write_task_progress(task, chunk, after_render=True)
        # 块渲染完，若任务的所有块都完成则写 .done，随后逐个合成
        _mark_task_done_if_complete(output_dir, chunk, chunks)
        if task is not None:
            _compose_pending(task, composed)

    if task is not None and task.cancel_requested:
        task.status = "cancelled"
        task.error = "Export cancelled by user"
        return True
    if task is not None:
        _compose_pending(task, composed)
    return True


async def _run_blender_chunk(chunk_file: str, task: ExportTask | None = None) -> bool:
    """调 Blender 渲染一个块（每次独立进程，强制释放累积资源）。"""
    command = [
        "blender", "--background",
        "--python", str(EXPORT_VIDEO_SCRIPT),
        "--",
        chunk_file,
    ]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    if task is not None:
        task.current_process = process
    try:
        stdout_bytes, stderr_bytes = await process.communicate()
    finally:
        if task is not None:
            task.current_process = None
    if process.returncode != 0:
        if task is not None and task.cancel_requested:
            return True  # 用户取消，不算错误
        error_message = stderr_bytes.decode() or stdout_bytes.decode() or "Unknown error"
        raise RuntimeError(f"Blender video export failed: {error_message[:500]}")
    return True


def _write_task_progress(task: ExportTask, chunk: dict, after_render: bool = False):
    """更新 task 的进度字段（export_status 直接读 task；渲染阶段帧进度以块为单位跳变）。"""
    if not task.output_dir:
        return
    total_frames = 0
    manifest_file = os.path.join(task.output_dir, "manifest.json")
    if os.path.isfile(manifest_file):
        try:
            with open(manifest_file) as file_handle:
                manifest = json.load(file_handle)
            for entry in manifest.get("tasks", []):
                if entry.get("name") == chunk["task_name"]:
                    total_frames = entry.get("frame_count", 0)
                    break
        except (json.JSONDecodeError, OSError):
            pass
    task_frame_start = chunk.get("task_frame_start", chunk["frame_start"])
    if after_render:
        current_frame = chunk["frame_end"] - task_frame_start + 1
    else:
        current_frame = max(0, chunk["frame_start"] - task_frame_start)
    task.current_file = chunk["task_name"]
    task.current_frame = current_frame
    task.current_total_frames = total_frames


def _mark_task_done_if_complete(output_dir: str, chunk: dict, chunks: list):
    """若某任务的所有块都渲染完（每块最后帧文件存在），写 .done 标记。"""
    task_name = chunk["task_name"]
    frames_dir = chunk["frames_dir"]
    for candidate in chunks:
        if candidate["task_name"] != task_name:
            continue
        last_frame_file = os.path.join(frames_dir, f"frame_{candidate['frame_end']:04d}.png")
        if not os.path.isfile(last_frame_file):
            return
    marker = os.path.join(frames_dir, ".done")
    if not os.path.isfile(marker):
        with open(marker, "w") as file_handle:
            file_handle.write("done")


def _load_fps(export_hash: str) -> int:
    """读 shot metadata 的帧率（默认 24）。"""
    metadata = load_shot_metadata(export_hash)
    if metadata:
        fps = metadata.get("frames_per_second")
        if fps:
            return int(fps)
    return 24


def _compose_pending(task: ExportTask, composed: set[str]):
    """逐个合成已渲染完（.done 标记存在）但未合成的文件，追加到 task.files。"""
    if not task.output_dir:
        return
    manifest_file = os.path.join(task.output_dir, "manifest.json")
    if not os.path.isfile(manifest_file):
        return
    try:
        with open(manifest_file) as file_handle:
            manifest = json.load(file_handle)
    except (json.JSONDecodeError, OSError):
        return
    fps = manifest.get("fps", 24)
    for entry in manifest.get("tasks", []):
        name = entry.get("name")
        if not name or name in composed:
            continue
        marker = os.path.join(entry.get("frames_dir", ""), ".done")
        if not os.path.isfile(marker):
            continue
        try:
            compose_single(entry, task.output_dir, fps)
        except Exception as error:
            task.status = "error"
            task.error = f"Compose failed for {name}: {error}"
            return
        composed.add(name)
        mp4_path = os.path.join(task.output_dir, f"{name}.mp4")
        task.current_file = name
        task.files.append(
            {
                "filename": f"{name}.mp4",
                "content_base64": base64.b64encode(Path(mp4_path).read_bytes()).decode(),
            }
        )
        task.completed_files += 1


def next_blend_version(directory: Path) -> int:
    """返回下一个 blend 版本号（scene_vN.blend 的 N，从 2 起）。"""
    version_numbers = []
    for file_path in directory.iterdir():
        name = file_path.name
        if name.startswith("scene_v") and name.endswith(".blend"):
            try:
                version_numbers.append(int(name[len("scene_v"):-len(".blend")]))
            except ValueError:
                pass
    return (max(version_numbers) if version_numbers else 1) + 1


class EditRequest(BaseModel):
    segments: list[dict]
    target_positions: dict[str, list[float]] | None = None


class ExportBlendRequest(BaseModel):
    chat_name: str = ""


def _resolve_source_blend(export_hash: str) -> Path:
    """读当前 shot 的源 blend 路径（chat/upload 统一）。"""
    current_metadata = load_shot_metadata(export_hash)
    if current_metadata is None:
        raise HTTPException(status_code=404, detail="Shot not found")
    source = current_metadata.get("source")
    if source and source.get("type") == "upload":
        source_blend = _resolve_upload_blend(source)
        if source_blend is None or not source_blend.is_file():
            raise HTTPException(status_code=404, detail="源 blend 不存在，请重新上传")
        return source_blend
    if source and source.get("type") == "chat":
        folder = _resolve_chat_folder(source)
        if folder is None:
            raise HTTPException(status_code=404, detail="该 shot 无源信息（旧数据），请重新生成")
        source_blend = get_latest_blend(folder)
        if source_blend is None:
            raise HTTPException(status_code=404, detail="源 blend 不存在（源目录为空）")
        return source_blend
    raise HTTPException(
        status_code=404,
        detail="该 shot 无源信息（旧数据），请重新上传或重新生成",
    )


@application.post("/api/shots/{export_hash}/export-blend")
async def export_blend(export_hash: str, request: ExportBlendRequest):
    """复制当前 blend：读源 blend，返回命名后的文件内容（前端写入所选目录）。"""
    source_blend = _resolve_source_blend(export_hash)
    filename = (
        f"{request.chat_name}_{source_blend.name}" if request.chat_name else source_blend.name
    )
    content = source_blend.read_bytes()
    return {"filename": filename, "content_base64": base64.b64encode(content).decode()}


class ExportMp4Request(BaseModel):
    chat_name: str = ""
    blend_prefix: str = ""
    resolution: str = "1080p"


@dataclass
class ExportTask:
    task_id: str
    export_hash: str
    resolution: str
    total_files: int
    source_blend: str
    segments: list
    status: str = "rendering"
    completed_files: int = 0
    current_file: str | None = None
    current_frame: int = 0
    current_total_frames: int = 0
    files: list = field(default_factory=list)
    error: str | None = None
    output_dir: str | None = None
    cancel_requested: bool = False
    current_process: asyncio.subprocess.Process | None = None


EXPORT_TASKS: dict[str, ExportTask] = {}


@application.post("/api/shots/{export_hash}/export-mp4")
async def export_mp4(export_hash: str, request: ExportMp4Request):
    """启动异步导出任务，返回 task_id。"""
    source_blend = _resolve_source_blend(export_hash)
    metadata = load_shot_metadata(export_hash)
    segments = (metadata or {}).get("segments", [])

    # 总文件数 = 每个有段相机 1 整段 + N 段
    segment_counts: dict[str, int] = {}
    for segment in segments:
        name = segment.get("camera_name")
        if name:
            segment_counts[name] = segment_counts.get(name, 0) + 1
    total_files = sum(1 + count for count in segment_counts.values())

    task = ExportTask(
        task_id=uuid.uuid4().hex,
        export_hash=export_hash,
        resolution=request.resolution,
        total_files=total_files,
        source_blend=str(source_blend),
        segments=segments,
    )
    EXPORT_TASKS[task.task_id] = task
    asyncio.create_task(_run_export_task(task))
    return {"task_id": task.task_id}


@application.get("/api/shots/export-status/{task_id}")
async def export_status(task_id: str):
    """返回导出任务的进度 + 已完成文件。"""
    task = EXPORT_TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "status": task.status,
        "progress": {
            "completed_files": task.completed_files,
            "total_files": task.total_files,
            "current_file": task.current_file,
            "current_frame": task.current_frame,
            "current_total_frames": task.current_total_frames,
        },
        "files": task.files,
        "error": task.error,
    }


@application.post("/api/shots/export-cancel/{task_id}")
async def export_cancel(task_id: str):
    """取消导出任务：标记取消 + kill 当前 Blender 子进程。"""
    task = EXPORT_TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task.cancel_requested = True
    if task.current_process is not None:
        try:
            task.current_process.kill()
        except ProcessLookupError:
            pass
    return {"ok": True}


async def _run_export_task(task: ExportTask):
    """后台渲染 + 合成，更新 task 状态。"""
    try:
        output_dir = tempfile.mkdtemp(prefix="export_mp4_")
        task.output_dir = output_dir
        description = {
            "blend": task.source_blend,
            "output_dir": output_dir,
            "segments": task.segments,
            "resolution": task.resolution,
            "fps": _load_fps(task.export_hash),
        }
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as temp_file:
            json.dump(description, temp_file)
            desc_file = temp_file.name
        try:
            await run_export_video(desc_file, task)
        finally:
            try:
                os.unlink(desc_file)
            except OSError:
                pass

        # 渲染 + 逐个合成已在 run_export_video 内完成
        task.current_file = None
        task.current_frame = 0
        task.current_total_frames = 0
        if not task.cancel_requested:
            task.status = "done"
    except Exception as error:  # noqa: BLE001 - 后台任务兜底，避免未处理异常
        task.status = "error"
        task.error = str(error)


def save_shot_metadata(export_hash: str, metadata: dict):
    """Save shot metadata to a JSON file inside the export directory."""
    cache_path = EXPORTS_ROOT / export_hash / CACHE_FILE
    with open(cache_path, "w") as file_handle:
        json.dump(metadata, file_handle, indent=2)


def load_shot_metadata(export_hash: str) -> dict | None:
    """Load shot metadata from cache. Returns None if not found."""
    cache_path = EXPORTS_ROOT / export_hash / CACHE_FILE
    if not cache_path.is_file():
        return None
    with open(cache_path) as file_handle:
        return json.load(file_handle)


def build_shot_metadata(export_hash: str, export_directory, gltf_filepath: str) -> dict:
    """构建完整 shot 元数据：解析 glTF + 合并 sidecar（frame aspect / segments）。

    「上传」和「重新加载」两条路径共用此函数，保证 segments / duration
    两边一致地从 sidecar 合并。
    """
    metadata = parse_gltf_for_metadata(gltf_filepath)
    metadata["export_hash"] = export_hash
    metadata["gltf_output_url"] = f"/static/exports/{export_hash}/{GLTF_OUTPUT_NAME}"

    frame_aspect = read_frame_aspect(str(export_directory))
    if frame_aspect:
        metadata["frame_aspect"] = frame_aspect

    segments_sidecar = read_segments_sidecar(str(export_directory))
    if segments_sidecar is not None:
        segments_result = parse_segments_sidecar(segments_sidecar)
        metadata["segments"] = segments_result["segments"]
        # 镜头段动画用绝对时间，glTF 各 animation 的 max time 不再等于总时长；
        # 真实总时长 = 段的最大绝对 end_time。
        segment_end_times = [segment["end_time"] for segment in segments_result["segments"]]
        if segment_end_times:
            metadata["duration_seconds"] = round(max(segment_end_times), 3)

    return metadata


async def ingest_blend(blend_path: str, source: dict | None = None) -> dict:
    """导出 .blend → gltf + metadata，返回 shot 元数据。

    exports 只存渲染产物（gltf/bin/metadata），不再保留 blend——源 blend 由
    调用方管理（生成在 generate/output/，上传在 generate/upload_output/）。
    source 记录该 shot 的源（type + 路径），保存回存时据此定位源 blend。
    """
    export_hash = compute_file_hash(blend_path)
    export_directory = EXPORTS_ROOT / export_hash
    export_directory.mkdir(parents=True, exist_ok=True)
    await run_export(blend_path, str(export_directory))

    gltf_filepath = str(export_directory / GLTF_OUTPUT_NAME)
    if not os.path.isfile(gltf_filepath):
        raise RuntimeError("Export completed but scene.gltf was not created")

    metadata = build_shot_metadata(export_hash, export_directory, gltf_filepath)
    if source is not None:
        metadata["source"] = source
    save_shot_metadata(export_hash, metadata)
    enforce_disk_quota()
    return metadata


@application.post("/api/shots")
async def upload_shot(file: UploadFile = File(...), force: bool = False):
    """Upload a .blend file, export to glTF, return shot metadata.
    
    Query params:
        force: if true, skip cache and re-export even if hash matches.
    """
    # Validate file extension
    original_filename = file.filename or "unknown"
    if not original_filename.lower().endswith(".blend"):
        raise HTTPException(
            status_code=422,
            detail="Only .blend files are accepted. "
                   f"Received: {original_filename}",
        )

    # Save uploaded file to a temp location
    with tempfile.NamedTemporaryFile(suffix=".blend", delete=False) as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_filepath = temp_file.name

    try:
        # Compute hash for deduplication
        export_hash = compute_file_hash(temp_filepath)

        # Check cache (skip if force=true)
        if not force:
            cached_metadata = load_shot_metadata(export_hash)
            if cached_metadata is not None:
                # 缓存命中：chat 源直接返回（源由 generate/reload 管理）。
                # upload 源：file 字段有效 → 文件缺失则补回原 file；
                # file 字段无效（source 缺失 / 旧 folder 字段）→ 重建新 file 并回填 metadata。
                source = cached_metadata.get("source")
                if source and source.get("type") == "chat":
                    return cached_metadata
                source_blend = _resolve_upload_blend(source)
                if source_blend is not None:
                    if source_blend.is_file():
                        return cached_metadata
                    source_blend.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(temp_filepath, str(source_blend))
                    return cached_metadata
                filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.blend"
                upload_root = get_upload_output_root()
                upload_root.mkdir(parents=True, exist_ok=True)
                dest_blend = upload_root / filename
                shutil.copy(temp_filepath, str(dest_blend))
                cached_metadata["source"] = {"type": "upload", "file": filename}
                save_shot_metadata(export_hash, cached_metadata)
                return cached_metadata
        else:
            # Remove old export before re-exporting
            export_directory = EXPORTS_ROOT / export_hash
            if export_directory.exists():
                shutil.rmtree(export_directory)

        # 上传源留存：源文件与保存文件统一扁平放 generate/upload_output/<时间戳>.blend
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.blend"
        upload_root = get_upload_output_root()
        upload_root.mkdir(parents=True, exist_ok=True)
        dest_blend = upload_root / filename
        shutil.copy(temp_filepath, str(dest_blend))

        return await ingest_blend(
            temp_filepath,
            source={"type": "upload", "file": filename},
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_filepath)
        except OSError:
            pass


@application.post("/api/shots/{export_hash}/edit")
async def edit_shot(export_hash: str, request: EditRequest):
    """整体回存：用编辑态完整 segments 重建 blend，重新导出，返回新 metadata。"""
    payload = parse_full_edit(request.segments, request.target_positions)

    # 读当前 shot 的源信息（保存回存时据此定位源 blend）
    current_metadata = load_shot_metadata(export_hash)
    if current_metadata is None:
        raise HTTPException(status_code=404, detail="Shot not found")
    source = current_metadata.get("source")

    # 按源类型定位源 blend 与输出路径
    if source and source.get("type") == "upload":
        # 上传源：读 upload_output/<file>，保存输出新的扁平文件（成为新源）
        source_blend = _resolve_upload_blend(source)
        if source_blend is None or not source_blend.is_file():
            raise HTTPException(status_code=404, detail="源 blend 不存在，请重新上传")
        upload_root = get_upload_output_root()
        upload_root.mkdir(parents=True, exist_ok=True)
        output_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.blend"
        output_blend = upload_root / output_filename
        new_source = {"type": "upload", "file": output_filename}
    elif source and source.get("type") == "chat":
        # 聊天源：读 output/<folder> 最新，写回 scene_vN 版本
        folder = _resolve_chat_folder(source)
        if folder is None:
            raise HTTPException(status_code=404, detail="该 shot 无源信息（旧数据），请重新生成")
        source_blend = get_latest_blend(folder)
        if source_blend is None:
            raise HTTPException(status_code=404, detail="源 blend 不存在（源目录为空）")
        version = next_blend_version(folder)
        output_blend = folder / f"scene_v{version}.blend"
        new_source = source
    else:
        raise HTTPException(
            status_code=404,
            detail="该 shot 无源信息（旧数据），请重新上传或重新生成",
        )

    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as temp_file:
        json.dump(payload, temp_file)
        payload_file = temp_file.name

    try:
        await run_apply_edit(str(source_blend), payload_file, str(output_blend))
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error))
    finally:
        try:
            os.unlink(payload_file)
        except OSError:
            pass

    # 重新导出新 blend → 新 metadata（upload 源 source 更新为新文件，chat 源不变）
    try:
        return await ingest_blend(str(output_blend), source=new_source)
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error))


def _blend_to_script_name(blend_filename: str) -> str:
    """scene.blend → script.py；scene_vN.blend → script_vN.py。"""
    if blend_filename == "scene.blend":
        return "script.py"
    version = blend_filename[len("scene_v"):-len(".blend")]
    return f"script_v{version}.py"


@application.get("/api/shots/{export_hash}/blends")
async def list_blends(export_hash: str):
    """返回该 shot 源目录下的 blend 版本列表（按 mtime 排序，最新在末）。"""
    current_metadata = load_shot_metadata(export_hash)
    if current_metadata is None:
        raise HTTPException(status_code=404, detail="Shot not found")
    source = current_metadata.get("source")

    # 只有 chat 源有版本列表（upload 源是扁平单文件，无版本）
    folder = _resolve_chat_folder(source)
    if folder is None or not folder.is_dir():
        return {"blends": [], "latest": None}

    blends = []
    for file_path in sorted(folder.iterdir()):
        if file_path.suffix != ".blend":
            continue
        script_name = _blend_to_script_name(file_path.name)
        blends.append(
            {
                "filename": file_path.name,
                "mtime": file_path.stat().st_mtime,
                "blend_hash": compute_file_hash(str(file_path)),
                # 有对应 script_vN.py = AI 生成；无 = 直接改 blend（手动/AI 改 blend）
                "has_script": (folder / script_name).exists(),
            }
        )
    blends.sort(key=lambda blend: blend["mtime"])
    latest = blends[-1]["filename"] if blends else None
    return {"blends": blends, "latest": latest}


@application.get("/api/shots/{export_hash}")
async def get_shot_metadata(export_hash: str):
    """Get cached shot metadata by export hash."""
    metadata = load_shot_metadata(export_hash)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Shot not found")
    return metadata


# Mount static files for exports
application.mount(
    "/static/exports",
    StaticFiles(directory=str(EXPORTS_ROOT)),
    name="static_exports",
)
