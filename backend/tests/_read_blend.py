"""辅助脚本：读 .blend 状态（frame_end / 相机 NLA track 名 / 全部 action 名），输出 JSON。

用法:
    blender --background --python _read_blend.py -- <blend> <check>

check 取值:
    frame_end    -> {"frame_end": int}
    nla_tracks   -> {"nla_tracks": [str, ...]}   （第一个相机的 NLA track 名）
    actions      -> {"actions": [str, ...]}      （全部 action 名，排序）
"""
import bpy
import json
import sys


def main():
    argv = sys.argv
    separator_index = argv.index("--")
    args = argv[separator_index + 1:]
    blend_path, check = args[0], args[1]

    bpy.ops.wm.open_mainfile(filepath=blend_path)
    result = {}
    if check == "frame_end":
        result["frame_end"] = bpy.context.scene.frame_end
    elif check == "nla_tracks":
        camera = next((obj for obj in bpy.data.objects if obj.type == "CAMERA"), None)
        result["nla_tracks"] = (
            [track.name for track in camera.animation_data.nla_tracks]
            if camera is not None and camera.animation_data is not None
            else []
        )
    elif check == "actions":
        result["actions"] = sorted(action.name for action in bpy.data.actions)
    elif check == "rotation":
        # 第一个相机、第一个 NLA strip 的 rotation_euler 首帧值（度，3 分量）
        import math
        camera = next((obj for obj in bpy.data.objects if obj.type == "CAMERA"), None)
        rotation = [0.0, 0.0, 0.0]
        if camera is not None and camera.animation_data is not None:
            for track in camera.animation_data.nla_tracks:
                for strip in track.strips:
                    if strip.action is not None:
                        for axis in range(3):
                            fcurve = strip.action.fcurves.find("rotation_euler", index=axis)
                            if fcurve is not None and fcurve.keyframe_points:
                                rotation[axis] = math.degrees(fcurve.keyframe_points[0].co[1])
                        result["rotation"] = [round(v, 2) for v in rotation]
                        print(json.dumps(result))
                        return
        result["rotation"] = rotation
    print(json.dumps(result))


if __name__ == "__main__":
    main()
