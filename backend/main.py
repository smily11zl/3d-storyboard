"""FastAPI application for Shot Viewer — .blend upload, glTF export, and static serving."""
import asyncio
import hashlib
import json
import os
import shutil
import tempfile
import time
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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPORT_SCRIPT = PROJECT_ROOT / "backend" / "export_shot.py"
APPLY_EDIT_SCRIPT = PROJECT_ROOT / "backend" / "apply_edit.py"

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
    target_positions: dict[str, list[float]]


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
        blends.append(
            {
                "filename": file_path.name,
                "mtime": file_path.stat().st_mtime,
                "blend_hash": compute_file_hash(str(file_path)),
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
