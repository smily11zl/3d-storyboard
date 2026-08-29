"""Integration tests for backend/apply_edit.py — Blender apply script."""
import json
import os
import subprocess
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
APPLY_SCRIPT = os.path.join(PROJECT_ROOT, "backend", "apply_edit.py")
READ_BLEND_SCRIPT = os.path.join(PROJECT_ROOT, "backend", "tests", "_read_blend.py")
FIXTURES_DIR = os.path.join(PROJECT_ROOT, "backend", "tests")
BLENDER_BIN = "blender"


def run_apply(blend_path, payload, output_blend):
    """Run apply_edit.py via Blender headless."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as file_handle:
        json.dump(payload, file_handle)
        payload_file = file_handle.name
    try:
        command = [
            BLENDER_BIN, "--background", "--python", APPLY_SCRIPT, "--",
            blend_path, payload_file, output_blend,
        ]
        return subprocess.run(command, capture_output=True, text=True, timeout=120)
    finally:
        os.unlink(payload_file)


def read_blend_state(blend_path, check):
    """Read blend state via _read_blend.py; returns parsed JSON dict."""
    command = [
        BLENDER_BIN, "--background", "--python", READ_BLEND_SCRIPT, "--",
        blend_path, check,
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    for line in reversed(result.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"No JSON in _read_blend.py output:\n{result.stdout}\n{result.stderr}")


def _segment(**overrides):
    segment = {
        "camera_name": "MainCamera",
        "segment_name": "seg_01",
        "start_time": 0.0,
        "end_time": 3.0,
        "start_pose": {"position": [0, 1, 2], "rotation": [0, 0, 0]},
        "end_pose": {"position": [2, 1, 2], "rotation": [0, 0, 0]},
        "orientation_mode": "interpolate",
        "interpolation": {"position": "LINEAR", "rotation": "LINEAR"},
    }
    segment.update(overrides)
    return segment


def test_apply_updates_frame_end_to_last_segment():
    """保存后 scene.frame_end 拉长到最末段结束帧（新增段不再播放不到）。"""
    fixture_path = os.path.join(FIXTURES_DIR, "fixture_minimal.blend")
    segments = [
        _segment(),
        _segment(
            segment_name="seg_02",
            start_time=3.0,
            end_time=9.0,
            start_pose={"position": [2, 1, 2], "rotation": [0, 0, 0]},
            end_pose={"position": [5, 1, 2], "rotation": [0, 0, 0]},
        ),
    ]
    with tempfile.TemporaryDirectory() as output_directory:
        output_blend = os.path.join(output_directory, "out.blend")
        result = run_apply(
            fixture_path, {"segments": segments, "target_positions": {}}, output_blend
        )
        assert result.returncode == 0, f"apply failed:\nSTDERR: {result.stderr}"
        state = read_blend_state(output_blend, "frame_end")
        assert state["frame_end"] == 216, f"expected frame_end 216 (9s * 24fps), got {state['frame_end']}"


def test_apply_twice_no_action_name_drift():
    """连续两次保存，段名不累积 .001（残留 action 已清理）。"""
    fixture_path = os.path.join(FIXTURES_DIR, "fixture_minimal.blend")
    segments = [
        _segment(),
        _segment(
            segment_name="seg_02",
            start_time=3.0,
            end_time=6.0,
            start_pose={"position": [2, 1, 2], "rotation": [0, 0, 0]},
            end_pose={"position": [5, 1, 2], "rotation": [0, 0, 0]},
        ),
    ]
    payload = {"segments": segments, "target_positions": {}}
    with tempfile.TemporaryDirectory() as output_directory:
        out1 = os.path.join(output_directory, "out1.blend")
        out2 = os.path.join(output_directory, "out2.blend")
        assert run_apply(fixture_path, payload, out1).returncode == 0
        assert run_apply(out1, payload, out2).returncode == 0
        state = read_blend_state(out2, "nla_tracks")
        assert state["nla_tracks"] == ["seg_01", "seg_02"], (
            f"段名漂移了: {state['nla_tracks']}"
        )


def test_apply_rotation_roll_maps_to_rz():
    """改 RZ（绕竖直轴滚转）→ blend rotation_euler 应为 RZ=20（intrinsic 约定）。

    前端 THREE.Euler 是 intrinsic（q = qx·qy·qz），与 Blender rotation_euler 一致；
    保存端必须用同一约定解释欧拉，否则「滚转(RZ)」会被错解成「摆钟(RY)」。
    """
    import math

    fixture_path = os.path.join(FIXTURES_DIR, "fixture_minimal.blend")
    rx = -math.pi / 2
    rz = math.radians(20)
    segments = [
        _segment(
            start_pose={"position": [0, 1, 2], "rotation": [rx, 0, rz]},
            end_pose={"position": [0, 1, 2], "rotation": [rx, 0, rz]},
        ),
    ]
    with tempfile.TemporaryDirectory() as output_directory:
        output_blend = os.path.join(output_directory, "out.blend")
        result = run_apply(
            fixture_path, {"segments": segments, "target_positions": {}}, output_blend
        )
        assert result.returncode == 0, f"apply failed:\nSTDERR: {result.stderr}"
        state = read_blend_state(output_blend, "rotation")
        assert state["rotation"] == [0.0, 0.0, 20.0], (
            f"改 RZ 滚转应得到 blend RZ=20，实际 {state['rotation']}"
        )


def test_apply_rotation_pitch_maps_to_ry():
    """改 RY（绕前后轴摆动）→ blend rotation_euler 应为 RY=20（intrinsic 约定）。"""
    import math

    fixture_path = os.path.join(FIXTURES_DIR, "fixture_minimal.blend")
    rx = -math.pi / 2
    ry = math.radians(20)
    segments = [
        _segment(
            start_pose={"position": [0, 1, 2], "rotation": [rx, ry, 0]},
            end_pose={"position": [0, 1, 2], "rotation": [rx, ry, 0]},
        ),
    ]
    with tempfile.TemporaryDirectory() as output_directory:
        output_blend = os.path.join(output_directory, "out.blend")
        result = run_apply(
            fixture_path, {"segments": segments, "target_positions": {}}, output_blend
        )
        assert result.returncode == 0, f"apply failed:\nSTDERR: {result.stderr}"
        state = read_blend_state(output_blend, "rotation")
        assert state["rotation"] == [0.0, 20.0, 0.0], (
            f"改 RY 摆钟应得到 blend RY=20，实际 {state['rotation']}"
        )
