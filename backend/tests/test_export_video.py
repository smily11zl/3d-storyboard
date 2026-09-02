"""Tests for video composition (render PNG frames → MP4 via imageio-ffmpeg)."""
import asyncio
import json

from pathlib import Path

import pytest


def test_compose_videos_synthesizes_mp4(monkeypatch, tmp_path):
    """读 manifest.json，用 ffmpeg 把每任务的 PNG 帧合成 MP4，返回产出路径。"""
    from backend import export_video_service

    output_dir = tmp_path / "out"
    frames_dir = output_dir / "frames" / "cam_01_full"
    frames_dir.mkdir(parents=True)
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fps": 30,
                "tasks": [
                    {
                        "name": "cam_01_full",
                        "frames_dir": str(frames_dir),
                        "frame_start": 0,
                        "frame_count": 10,
                    },
                    {
                        "name": "cam_01_seg_01",
                        "frames_dir": str(output_dir / "frames" / "cam_01_seg_01"),
                        "frame_start": 0,
                        "frame_count": 5,
                    },
                ],
            }
        )
    )

    captured_commands = []

    def fake_run(command, check=True, capture_output=False):
        captured_commands.append(command)
        Path(command[-1]).write_bytes(b"fake mp4")
        return None

    monkeypatch.setattr(export_video_service.subprocess, "run", fake_run)
    monkeypatch.setattr(
        export_video_service.imageio_ffmpeg, "get_ffmpeg_exe", lambda: "/fake/ffmpeg"
    )

    produced = export_video_service.compose_videos(str(output_dir))

    assert produced == [
        str(output_dir / "cam_01_full.mp4"),
        str(output_dir / "cam_01_seg_01.mp4"),
    ]
    assert len(captured_commands) == 2
    assert captured_commands[0][0] == "/fake/ffmpeg"
    assert (output_dir / "cam_01_full.mp4").read_bytes() == b"fake mp4"


@pytest.mark.asyncio
async def test_export_mp4_returns_task_id_and_status(monkeypatch, tmp_path):
    """POST /export-mp4 启动异步任务返回 task_id；GET /export-status 返回进度。"""
    from backend import generate
    from backend import main as main_module
    from backend.main import ExportMp4Request

    exports_root = tmp_path / "exports"
    exports_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(main_module, "EXPORTS_ROOT", exports_root)
    monkeypatch.setattr(generate, "GENERATE_ROOT", tmp_path / "generate")

    folder = tmp_path / "generate" / "output" / "20260817_115113"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "scene.blend").write_bytes(b"fake blend")

    export_hash = "a" * 64
    export_dir = exports_root / export_hash
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "shot_metadata.json").write_text(
        json.dumps(
            {
                "export_hash": export_hash,
                "source": {"type": "chat", "folder": "20260817_115113"},
                "segments": [
                    {
                        "camera_name": "cam_01",
                        "segment_name": "seg_01",
                        "start_time": 0.0,
                        "end_time": 3.0,
                        "segment_type": "S",
                    },
                ],
            }
        )
    )

    async def fake_run_export_task(task):
        task.status = "done"
        task.completed_files = task.total_files
        task.files = [{"filename": "cam_01_full.mp4", "content_base64": "eA=="}]

    monkeypatch.setattr(main_module, "_run_export_task", fake_run_export_task)

    result = await main_module.export_mp4(
        export_hash,
        ExportMp4Request(chat_name="t", blend_prefix="s", resolution="1080p"),
    )

    task_id = result["task_id"]
    assert task_id in main_module.EXPORT_TASKS

    await asyncio.sleep(0)  # 让后台任务执行

    status = await main_module.export_status(task_id)
    assert status["status"] == "done"
    assert status["progress"]["completed_files"] == 2
    assert status["progress"]["total_files"] == 2
    assert status["files"] == [{"filename": "cam_01_full.mp4", "content_base64": "eA=="}]
