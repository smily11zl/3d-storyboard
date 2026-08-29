"""Integration tests for backend/export_shot.py — Blender glTF export script."""
import json
import os
import subprocess
import sys
import tempfile
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
EXPORT_SCRIPT = os.path.join(PROJECT_ROOT, "backend", "export_shot.py")
FIXTURES_DIR = os.path.join(PROJECT_ROOT, "backend", "tests")
BLENDER_BIN = "blender"


def run_export(blend_path, output_directory):
    """Run export_shot.py via Blender headless, return exit code and output."""
    command = [
        BLENDER_BIN,
        "--background",
        "--python", EXPORT_SCRIPT,
        "--",
        blend_path,
        output_directory,
    ]
    result = subprocess.run(
        command, capture_output=True, text=True, timeout=60,
        env={**os.environ, "PYTHONUNBUFFERED": "1"}
    )
    return result


def test_exports_gltf_with_camera_and_animation():
    """Export a .blend with camera + animation → verify .gltf structure."""
    fixture_path = os.path.join(FIXTURES_DIR, "fixture_minimal.blend")
    with tempfile.TemporaryDirectory() as output_directory:
        result = run_export(fixture_path, output_directory)

        assert result.returncode == 0, (
            f"Export failed (exit {result.returncode}):\n"
            f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )

        # Check output files exist
        gltf_path = os.path.join(output_directory, "scene.gltf")
        bin_path = os.path.join(output_directory, "scene.bin")
        assert os.path.isfile(gltf_path), f"Missing scene.gltf in {os.listdir(output_directory)}"
        assert os.path.isfile(bin_path), f"Missing scene.bin in {os.listdir(output_directory)}"

        # Parse glTF JSON
        with open(gltf_path) as file_handle:
            gltf_data = json.load(file_handle)

        # Verify cameras exist
        assert "cameras" in gltf_data, "glTF missing 'cameras' array"
        camera_count = len(gltf_data["cameras"])
        assert camera_count >= 1, f"Expected >=1 camera, got {camera_count}"

        # Verify at least one node references a camera
        camera_node_indices = [
            node_index for node_index, node in enumerate(gltf_data.get("nodes", []))
            if "camera" in node
        ]
        assert len(camera_node_indices) >= 1, (
            f"No node references a camera. Nodes: {gltf_data.get('nodes', [])}"
        )

        # Verify animations exist
        assert "animations" in gltf_data, "glTF missing 'animations' array"
        animation_count = len(gltf_data["animations"])
        assert animation_count >= 1, f"Expected >=1 animation, got {animation_count}"

        # Verify meshes exist (the cube)
        assert "meshes" in gltf_data, "glTF missing 'meshes' array"
        assert len(gltf_data["meshes"]) >= 1


def test_exports_without_camera():
    """Export a .blend with no camera → still exports scene successfully."""
    fixture_path = os.path.join(FIXTURES_DIR, "fixture_no_camera.blend")
    with tempfile.TemporaryDirectory() as output_directory:
        result = run_export(fixture_path, output_directory)

        assert result.returncode == 0, (
            f"Export failed (exit {result.returncode}):\n"
            f"STDERR: {result.stderr}"
        )

        gltf_path = os.path.join(output_directory, "scene.gltf")
        assert os.path.isfile(gltf_path)

        with open(gltf_path) as file_handle:
            gltf_data = json.load(file_handle)

        # Should still have meshes
        assert len(gltf_data.get("meshes", [])) >= 1, "Expected meshes even without camera"

        # Camera array may be absent or empty — both are acceptable
        camera_node_indices = [
            node_index for node_index, node in enumerate(gltf_data.get("nodes", []))
            if "camera" in node
        ]
        assert len(camera_node_indices) == 0, (
            f"Expected 0 camera nodes for no-camera .blend, got {camera_node_indices}"
        )


def test_fails_on_missing_blend():
    """Export a nonexistent .blend → should exit non-zero with error."""
    with tempfile.TemporaryDirectory() as output_directory:
        result = run_export("/nonexistent/path/file.blend", output_directory)

        assert result.returncode != 0, (
            f"Expected non-zero exit for missing file, got {result.returncode}"
        )
        combined_output = result.stdout + result.stderr
        assert len(combined_output) > 0, "Expected error message for missing file"


def test_export_skips_pure_influence_direct_action():
    """含纯 influence 直接 action 的相机 → glTF 不应导出它的烘焙动画。

    方案 A 的约束 influence 动画存在相机「直接 action」里。导出时若不清掉，
    glTF 导出器会把它烘焙成一条覆盖全时间轴的全局 rotation 动画，叠加污染各段朝向。
    """
    fixture_path = os.path.join(FIXTURES_DIR, "fixture_influence.blend")
    with tempfile.TemporaryDirectory() as output_directory:
        result = run_export(fixture_path, output_directory)
        assert result.returncode == 0, (
            f"Export failed (exit {result.returncode}):\n"
            f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )

        gltf_path = os.path.join(output_directory, "scene.gltf")
        with open(gltf_path) as file_handle:
            gltf_data = json.load(file_handle)

        animation_names = [
            animation.get("name", "") for animation in gltf_data.get("animations", [])
        ]
        assert "CameraInfluenceAction" not in animation_names, (
            f"纯 influence 直接 action 被错误导出: {animation_names}"
        )
        assert "CameraMove" in animation_names, (
            f"NLA strip 动画缺失: {animation_names}"
        )
