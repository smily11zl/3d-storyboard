"""Blend export: copy the current blend to a target folder with a {chat_name}_ prefix."""
from pathlib import Path

import shutil


def copy_blend_with_prefix(source_blend: Path, target_dir: Path, chat_name: str) -> Path:
    """复制 blend 到 target_dir，文件名加 `{chat_name}_` 前缀（chat_name 为空则保持原名），返回目标路径。"""
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / (f"{chat_name}_{source_blend.name}" if chat_name else source_blend.name)
    shutil.copy2(source_blend, target)
    return target
