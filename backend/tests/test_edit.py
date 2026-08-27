"""V5 回存整体提交解析测试 — parse_full_edit。"""
import pytest

from backend.edit_operations import parse_full_edit


def _segment(**overrides):
    segment = {
        "camera_name": "cam_01",
        "segment_name": "seg_01",
        "start_time": 0.0,
        "end_time": 3.0,
        "start_pose": {"position": [0, 1, 2], "rotation": [0, 0, 0]},
        "end_pose": {"position": [2, 1, 2], "rotation": [0, 0, 0]},
    }
    segment.update(overrides)
    return segment


def test_parse_segments_and_targets():
    result = parse_full_edit(
        [_segment(), _segment(segment_name="seg_02", start_time=3.0, end_time=6.0)],
        {"target_01": [1, 2, 3]},
    )
    assert len(result["segments"]) == 2
    assert result["segments"][0]["start_time"] == 0.0
    assert result["segments"][0]["start_pose"]["position"] == [0.0, 1.0, 2.0]
    assert result["segments"][1]["segment_name"] == "seg_02"
    assert result["target_positions"]["target_01"] == [1.0, 2.0, 3.0]


def test_segment_optional_fields_preserved():
    result = parse_full_edit(
        [
            _segment(
                orientation_mode="follow",
                constraint={"rotation": [{"type": "TRACK_TO", "target": "target_01"}]},
                interpolation={"position": "LINEAR", "rotation": "LINEAR"},
                segment_type="S",
            )
        ],
        {},
    )
    segment = result["segments"][0]
    assert segment["orientation_mode"] == "follow"
    assert segment["constraint"]["rotation"][0]["target"] == "target_01"
    assert segment["interpolation"]["position"] == "LINEAR"
    assert segment["segment_type"] == "S"


def test_segments_must_be_list():
    with pytest.raises(ValueError):
        parse_full_edit("not-a-list", {})


def test_target_positions_must_be_object():
    with pytest.raises(ValueError):
        parse_full_edit([], "not-a-dict")


def test_missing_segment_field_rejected():
    segment = _segment()
    del segment["end_pose"]
    with pytest.raises(ValueError):
        parse_full_edit([segment], {})


def test_invalid_vec3_rejected():
    with pytest.raises(ValueError):
        parse_full_edit(
            [_segment(start_pose={"position": [0, 1], "rotation": [0, 0, 0]})],
            {},
        )


def test_invalid_target_position_rejected():
    with pytest.raises(ValueError):
        parse_full_edit([], {"target_01": [1, 2]})
