"""FastAPI application for Shot Viewer — .blend upload, glTF export, and static serving."""
import asyncio
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.settings import router as settings_router
from backend.generate import router as generate_router

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPORT_SCRIPT = PROJECT_ROOT / "backend" / "export_shot.py"

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
        export_directory = EXPORTS_ROOT / export_hash

        # Check cache (skip if force=true)
        if not force:
            cached_metadata = load_shot_metadata(export_hash)
            if cached_metadata is not None:
                return cached_metadata
        else:
            # Remove old export before re-exporting
            import shutil
            if export_directory.exists():
                shutil.rmtree(export_directory)

        # Run Blender export
        export_directory.mkdir(parents=True, exist_ok=True)
        await run_export(temp_filepath, str(export_directory))

        # Parse glTF for metadata
        gltf_filepath = str(export_directory / GLTF_OUTPUT_NAME)
        if not os.path.isfile(gltf_filepath):
            raise HTTPException(
                status_code=500,
                detail="Export completed but scene.gltf was not created",
            )

        metadata = parse_gltf_for_metadata(gltf_filepath)
        metadata["export_hash"] = export_hash
        metadata["gltf_output_url"] = f"/static/exports/{export_hash}/{GLTF_OUTPUT_NAME}"
        frame_aspect = read_frame_aspect(str(export_directory))
        if frame_aspect:
            metadata["frame_aspect"] = frame_aspect

        # Save metadata cache
        save_shot_metadata(export_hash, metadata)

        # Enforce disk quota after import
        enforce_disk_quota()

        return metadata
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
