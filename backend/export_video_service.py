"""Video composition: turn Blender-rendered PNG frames into MP4 via imageio-ffmpeg."""
import json
import os
import subprocess
from pathlib import Path

import imageio_ffmpeg


def compose_single(task: dict, output_dir: str, fps: int) -> str:
    """合成单个任务的 PNG 帧为 MP4，返回 MP4 路径。"""
    output_path = Path(output_dir)
    frames_dir = task["frames_dir"]
    output_mp4 = output_path / f"{task['name']}.mp4"
    pattern = os.path.join(frames_dir, "frame_%04d.png")
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [
        ffmpeg, "-y",
        "-framerate", str(fps),
        "-start_number", str(task["frame_start"]),
        "-i", pattern,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(output_mp4),
    ]
    subprocess.run(command, check=True, capture_output=True)
    return str(output_mp4)


def compose_videos(output_dir: str) -> list[str]:
    """读 manifest.json，把每个任务的 PNG 帧合成 MP4，返回 MP4 路径列表（按 manifest 顺序）。"""
    output_dir = Path(output_dir)
    with open(output_dir / "manifest.json") as file_handle:
        manifest = json.load(file_handle)
    fps = manifest["fps"]
    produced = []
    for task in manifest["tasks"]:
        produced.append(compose_single(task, str(output_dir), fps))
    return produced
