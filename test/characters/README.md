# Characters 角色库

## 文件列表

| 文件 | 类型 | 骨骼 | 身高 | 朝向(rot=0) | 说明 |
|------|------|------|------|------|------|
| male_mixamo_stand.fbx | FBX | Mixamo 49骨骼 | ~2m | -Y | 男性站立 |
| female_mixamo_stand.fbx | FBX | Mixamo 49骨骼 | ~2m | -Y | 女性站立 |
| child_mixamo_stand.fbx | FBX | Mixamo 49骨骼 | ~1m | -Y | 小孩站立 |

## 场景搭建规范

### 门洞高度

门洞最低高度 = 最高角色的身高 + 0.4m 余量。

- 成年男女身高 2m → **门洞至少 2.4m**
- 如果角色可能跳跃或有帽子/头发装饰，再加 0.2m

### 墙壁高度

室内墙壁最低 = 门洞高度 + 0.3m（门上方墙体）。

- 门洞 2.4m + 门梁 0.15m + 上方墙 0.5m → **屋顶约 3m**

### 地面

地面统一放在 `z=0`，角色脚底对齐地面。

### 角色间距

- 面对面交谈：间距 1.5~3m（X轴偏移 ±1m 左右）
- 并排站立：间距 0.5~1m

## 骨骼结构（Mixamo标准，各49块）

```
Hips（根）
├── Spine → Spine1 → Spine2 → Neck → Head → HeadTop_End
├── LeftShoulder → LeftArm → LeftForeArm → LeftHand → 手指(拇指/食指/中指)
├── RightShoulder → RightArm → RightForeArm → RightHand → 手指(拇指/食指/中指)
├── LeftUpLeg → LeftLeg → LeftFoot → LeftToeBase → LeftToe_End
└── RightUpLeg → RightLeg → RightFoot → RightToeBase → RightToe_End
```

## 默认朝向

所有角色 `rot=0` 时面朝 **-Y** 方向。

```
rot=0    → 面朝 -Y（默认）
rot=90°  → 面朝 +X（右）
rot=-90° → 面朝 -X（左）
rot=180° → 面朝 +Y（反方向）
```

## 摆姿势示例

```python
import bpy

arm = bpy.data.objects["Armature"]
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='POSE')
pb = arm.pose.bones

# 手臂放下
pb['mixamorig:LeftArm'].rotation_euler = (0, 0, -1.4)
pb['mixamorig:RightArm'].rotation_euler = (0, 0, 1.4)

bpy.ops.object.mode_set(mode='OBJECT')
```

## 导入方式

```python
bpy.ops.import_scene.fbx(filepath="characters/male_mixamo_stand.fbx")
```

导入后网格和骨骼自动绑定，网格是骨架的子对象。
