"""V5 回存编辑请求解析 — 纯函数，无 Blender 依赖（可单测）。

回存采用「整体提交」：前端把编辑态完整数据（segments + target_positions）POST 给后端，
后端 apply_edit.py（Blender 脚本）整体重建相机动画（含 Y-up → Z-up 坐标转化）。
本模块只做解析 + 字段校验，把非法输入变成 ValueError。
"""
from __future__ import annotations

from typing import Any


def parse_full_edit(segments: Any, target_positions: Any = None) -> dict[str, Any]:
    """解析并校验完整回存 payload。返回规范化后的 {segments, target_positions}。

    target_positions 现为可选：每段 target 位置已随段 target_position 字段走。
    """
    if not isinstance(segments, list):
        raise ValueError("segments must be a list")
    parsed_segments: list[dict[str, Any]] = []
    for segment in segments:
        if not isinstance(segment, dict):
            raise ValueError("each segment must be an object")
        parsed_segments.append(_parse_segment(segment))

    parsed_targets: dict[str, list[float]] = {}
    if target_positions is not None:
        if not isinstance(target_positions, dict):
            raise ValueError("target_positions must be an object")
        for name, position in target_positions.items():
            if not isinstance(name, str):
                raise ValueError("target name must be a string")
            parsed_targets[name] = _parse_vec3(position)

    return {"segments": parsed_segments, "target_positions": parsed_targets}


def _parse_segment(segment: dict[str, Any]) -> dict[str, Any]:
    _require(
        segment,
        "camera_name",
        "segment_name",
        "start_time",
        "end_time",
        "start_pose",
        "end_pose",
    )
    parsed: dict[str, Any] = {
        "camera_name": segment["camera_name"],
        "segment_name": segment["segment_name"],
        "start_time": float(segment["start_time"]),
        "end_time": float(segment["end_time"]),
        "start_pose": _parse_pose(segment["start_pose"]),
        "end_pose": _parse_pose(segment["end_pose"]),
    }
    if "segment_type" in segment:
        parsed["segment_type"] = segment["segment_type"]
    if "constraint" in segment:
        parsed["constraint"] = segment["constraint"]
    if "interpolation" in segment:
        parsed["interpolation"] = segment["interpolation"]
    if "orientation_mode" in segment:
        parsed["orientation_mode"] = segment["orientation_mode"]
    else:
        # 旧缓存 segments 可能缺 orientation_mode：用 constraint 推导（与前端显示一致）。
        # 有 TRACK_TO 约束 → follow（约束 lookAt 驱动）；否则 interpolate（关键帧插值）。
        rotation_constraints = (segment.get("constraint") or {}).get("rotation", [])
        parsed["orientation_mode"] = (
            "follow"
            if any(entry.get("type") == "TRACK_TO" for entry in rotation_constraints)
            else "interpolate"
        )
    if "position_keyframes" in segment:
        parsed["position_keyframes"] = [
            {"time": float(keyframe["time"]), "position": _parse_vec3(keyframe["position"])}
            for keyframe in segment["position_keyframes"]
        ]
    if "rotation_keyframes" in segment:
        parsed["rotation_keyframes"] = [
            {"time": float(keyframe["time"]), "rotation": _parse_vec3(keyframe["rotation"])}
            for keyframe in segment["rotation_keyframes"]
        ]
    if "target_position" in segment and segment["target_position"] is not None:
        parsed["target_position"] = _parse_vec3(segment["target_position"])
    return parsed


def _require(operation: dict[str, Any], *fields: str) -> None:
    for field in fields:
        if field not in operation:
            raise ValueError(f"missing field: {field}")


def _parse_vec3(value: Any) -> list[float]:
    if not (isinstance(value, (list, tuple)) and len(value) == 3):
        raise ValueError(f"expected a 3-element vector, got: {value!r}")
    return [float(value[0]), float(value[1]), float(value[2])]


def _parse_pose(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("pose must be an object")
    _require(value, "position", "rotation")
    return {"position": _parse_vec3(value["position"]), "rotation": _parse_vec3(value["rotation"])}
