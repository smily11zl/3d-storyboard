"""V4 镜头段识别 — 读 segments.json sidecar，返回按 start_time 升序的段列表。"""


def parse_segments_sidecar(sidecar_json: dict) -> dict:
    """读 segments.json sidecar，返回按 start_time 升序的段列表。

    参数 sidecar_json 是 Blender 脚本（export_shot.py）读 NLA strips 后写的
    segments.json 内容，形如 {"segments": [{camera_name, start_time, end_time,
    start_pose, end_pose, segment_type}, ...]}。

    返回 {"segments": [...]}，segments 按 start_time 升序排序。
    轨道分组（按 camera_name）由前端完成。
    """
    segments = sidecar_json.get("segments", [])
    sorted_segments = sorted(segments, key=lambda segment: segment["start_time"])
    return {"segments": sorted_segments}
