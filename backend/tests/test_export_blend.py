"""Tests for blend copy (Export Blend) — non-destructive copy with a {chat_name}_ prefix."""
import os

from backend.export_blend import copy_blend_with_prefix


def test_copy_blend_with_prefix_copies_and_names(tmp_path):
    """复制 blend 到目标目录，文件名加 {chat_name}_ 前缀，内容一致。"""
    source = tmp_path / "scene_v3.blend"
    source.write_bytes(b"fake blend content")
    target_dir = tmp_path / "out"

    result = copy_blend_with_prefix(source, target_dir, "我的聊天")

    assert result == target_dir / "我的聊天_scene_v3.blend"
    assert result.is_file()
    assert result.read_bytes() == b"fake blend content"


def test_copy_blend_with_prefix_creates_target_dir(tmp_path):
    """目标目录不存在时自动创建。"""
    source = tmp_path / "scene.blend"
    source.write_bytes(b"x")
    target_dir = tmp_path / "nested" / "out"

    result = copy_blend_with_prefix(source, target_dir, "chat name")

    assert result.is_file()
    assert result.name == "chat name_scene.blend"


def test_copy_blend_with_prefix_keeps_source(tmp_path):
    """复制不改动源文件。"""
    source = tmp_path / "scene.blend"
    source.write_bytes(b"original")
    target_dir = tmp_path / "out"

    copy_blend_with_prefix(source, target_dir, "聊天")

    assert source.read_bytes() == b"original"


# --- 端点层：POST /export/blend ---

import base64
import json

import pytest


@pytest.mark.asyncio
async def test_export_blend_returns_named_content(monkeypatch, tmp_path):
    """聊天源：读最新 blend，返回 {chat_name}_ 前缀的文件名 + base64 内容。"""
    from backend import generate
    from backend import main as main_module
    from backend.main import ExportBlendRequest

    exports_root = tmp_path / "exports"
    exports_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(main_module, "EXPORTS_ROOT", exports_root)
    monkeypatch.setattr(generate, "GENERATE_ROOT", tmp_path / "generate")

    folder = tmp_path / "generate" / "output" / "20260817_115113"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "scene.blend").write_bytes(b"fake chat blend")

    export_hash = "a" * 64
    export_dir = exports_root / export_hash
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "shot_metadata.json").write_text(
        json.dumps(
            {"export_hash": export_hash, "source": {"type": "chat", "folder": "20260817_115113"}}
        )
    )

    result = await main_module.export_blend(
        export_hash, ExportBlendRequest(chat_name="我的聊天")
    )

    assert result["filename"] == "我的聊天_scene.blend"
    assert result["content_base64"] == base64.b64encode(b"fake chat blend").decode()


@pytest.mark.asyncio
async def test_export_blend_upload_source(monkeypatch, tmp_path):
    """上传源：读 upload_output/<file>，返回 {chat_name}_ 前缀命名。"""
    from backend import generate
    from backend import main as main_module
    from backend.main import ExportBlendRequest

    exports_root = tmp_path / "exports"
    exports_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(main_module, "EXPORTS_ROOT", exports_root)
    monkeypatch.setattr(generate, "GENERATE_ROOT", tmp_path / "generate")

    upload_root = tmp_path / "generate" / "upload_output"
    upload_root.mkdir(parents=True, exist_ok=True)
    source_filename = "20260821_131503_123456.blend"
    (upload_root / source_filename).write_bytes(b"upload blend content")

    export_hash = "b" * 64
    export_dir = exports_root / export_hash
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "shot_metadata.json").write_text(
        json.dumps(
            {"export_hash": export_hash, "source": {"type": "upload", "file": source_filename}}
        )
    )

    result = await main_module.export_blend(
        export_hash, ExportBlendRequest(chat_name="聊天A")
    )

    assert result["filename"] == f"聊天A_{source_filename}"
    assert result["content_base64"] == base64.b64encode(b"upload blend content").decode()


# --- 端点层：POST /export/mp4 已改为异步任务，见 test_export_video.py ---
