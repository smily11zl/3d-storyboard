"""V4 镜头段识别测试 — parse_segments_sidecar（读 segments.json sidecar 解析 + 排序）。"""
from backend.shot_segments import parse_segments_sidecar


def test_parse_single_segment_passthrough():
    """单段 → 字段完整透传。"""
    sidecar = {
        "segments": [
            {
                "camera_name": "cam_01",
                "start_time": 0.0,
                "end_time": 3.0,
                "start_pose": {"position": [0, 0, 5], "quaternion": [0, 0, 0, 1]},
                "end_pose": {"position": [0, 0, 2], "quaternion": [0, 0, 0, 1]},
                "segment_type": "S",
            }
        ]
    }
    result = parse_segments_sidecar(sidecar)

    assert len(result["segments"]) == 1
    segment = result["segments"][0]
    assert segment["camera_name"] == "cam_01"
    assert segment["start_time"] == 0.0
    assert segment["end_time"] == 3.0
    assert segment["segment_type"] == "S"
    assert segment["start_pose"]["position"] == [0, 0, 5]


def test_parse_adjacent_segments():
    """首尾相接（0-3, 3-5）两段都保留。"""
    sidecar = {
        "segments": [
            {"camera_name": "cam_01", "start_time": 0.0, "end_time": 3.0, "segment_type": "S"},
            {"camera_name": "cam_01", "start_time": 3.0, "end_time": 5.0, "segment_type": "C"},
        ]
    }
    result = parse_segments_sidecar(sidecar)

    assert len(result["segments"]) == 2


def test_parse_overlapping_segments_kept():
    """重叠（0-3, 2-5）两段都保留（轨道模型下不同相机的重叠是合法并行）。"""
    sidecar = {
        "segments": [
            {"camera_name": "cam_01", "start_time": 0.0, "end_time": 3.0, "segment_type": "S"},
            {"camera_name": "cam_02", "start_time": 2.0, "end_time": 5.0, "segment_type": "S"},
        ]
    }
    result = parse_segments_sidecar(sidecar)

    assert len(result["segments"]) == 2


def test_parse_fully_contained_overlap_kept():
    """完全包含（0-5, 1-4）两段都保留。"""
    sidecar = {
        "segments": [
            {"camera_name": "cam_01", "start_time": 0.0, "end_time": 5.0, "segment_type": "S"},
            {"camera_name": "cam_02", "start_time": 1.0, "end_time": 4.0, "segment_type": "S"},
        ]
    }
    result = parse_segments_sidecar(sidecar)

    assert len(result["segments"]) == 2


def test_parse_empty_segments():
    """空 segments → 空列表。"""
    result = parse_segments_sidecar({"segments": []})

    assert result["segments"] == []


def test_parse_segments_sorted_by_start_time():
    """乱序输入 → segments 按 start_time 升序输出。"""
    sidecar = {
        "segments": [
            {"camera_name": "cam_02", "start_time": 3.0, "end_time": 5.0, "segment_type": "S"},
            {"camera_name": "cam_01", "start_time": 0.0, "end_time": 3.0, "segment_type": "S"},
        ]
    }
    result = parse_segments_sidecar(sidecar)

    assert [segment["start_time"] for segment in result["segments"]] == [0.0, 3.0]
    assert result["segments"][0]["camera_name"] == "cam_01"
    assert result["segments"][1]["camera_name"] == "cam_02"


def test_interpolation_passthrough():
    """段带 interpolation 字段时透传。"""
    sidecar = {
        "segments": [
            {
                "camera_name": "cam_01",
                "start_time": 0.0,
                "end_time": 3.0,
                "segment_type": "S",
                "interpolation": {"position": "LINEAR", "rotation": "CONSTANT"},
            }
        ]
    }
    result = parse_segments_sidecar(sidecar)
    assert result["segments"][0]["interpolation"] == {"position": "LINEAR", "rotation": "CONSTANT"}


class _MockOwner:
    animation_data = None


class _MockConstraint:
    def __init__(self, type_name, influence=1.0):
        self.type = type_name
        self.influence = influence
        self.name = "mock_track"
        self.id_data = _MockOwner()


class _MockCamera:
    def __init__(self, constraints):
        self.constraints = constraints


def test_orientation_mode_track_to_is_follow():
    from backend.export_shot import _orientation_mode

    camera = _MockCamera([_MockConstraint("TRACK_TO", influence=1.0)])
    meta = {"rotation": [{"type": "TRACK_TO", "target": "target_01"}]}
    assert _orientation_mode(camera, 1, 72, meta) == "follow"


def test_orientation_mode_track_to_zero_influence_is_interpolate():
    from backend.export_shot import _orientation_mode

    camera = _MockCamera([_MockConstraint("TRACK_TO", influence=0.0)])
    meta = {"rotation": [{"type": "TRACK_TO", "target": "target_01"}]}
    assert _orientation_mode(camera, 217, 288, meta) == "interpolate"


def test_orientation_mode_no_constraint_is_interpolate():
    from backend.export_shot import _orientation_mode

    assert _orientation_mode(None, 0, 0, {}) == "interpolate"


def test_orientation_mode_non_track_to_is_interpolate():
    from backend.export_shot import _orientation_mode

    meta = {"rotation": [{"type": "COPY_ROTATION", "target": "t"}]}
    assert _orientation_mode(None, 0, 0, meta) == "interpolate"
