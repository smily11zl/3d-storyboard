"""
test_glm_01.py
测试：用 GLM 模型生成 Blender 分镜代码，然后自动渲染。

流程：
1. 给 GLM 一个分镜描述
2. GLM 返回 Blender Python 代码
3. 保存代码到文件
4. 调用 Blender 无头渲染
"""
import os
import re
import sys
import subprocess
from pathlib import Path

# ============================================================
# 配置
# ============================================================
PROJECT_DIR = Path("/Users/zengle/Documents/storyboard-3d-pipeline")
SHOTS_DIR = PROJECT_DIR / "shots"
RENDER_DIR = PROJECT_DIR / "render"

# GLM API 配置（从 .env 读取）
GLM_API_KEY = os.environ.get("GLM_API_KEY", "")
GLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
GLM_MODEL = "glm-4-plus"

if not GLM_API_KEY:
    # 尝试从 .env 文件读取
    env_path = Path.home() / ".hermes" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("GLM_API_KEY="):
                GLM_API_KEY = line.split("=", 1)[1].strip()
                break

if not GLM_API_KEY:
    print("错误：未找到 GLM_API_KEY，请在 .env 中设置")
    sys.exit(1)

print(f"✓ 找到 GLM_API_KEY: {GLM_API_KEY[:8]}...")

# ============================================================
# 分镜描述（给 LLM 的输入）
# ============================================================
SHOT_DESCRIPTION = """
场景：两个人对话的过肩镜头

人物布局：
- 蓝衣人物（CharB）：站在前方 y=1.0，面向镜头方向（转180度），画面主体
- 红衣人物（CharA）：站在靠近镜头的右侧 x=0.8, y=-1.5，侧转面向蓝衣

镜头要求：
- 过肩镜头，从红衣右肩后方拍摄蓝衣
- 镜头起始位置：(0.8, -4.0, 1.6)
- 镜头终点位置：(0.6, -2.2, 1.6)
- 镜头在 60 帧内从起点推到终点，60-72帧定格不动
- 注视目标：蓝衣头部 (0, 1.0, 1.9)
- 使用贝塞尔缓入缓出
- 镜头焦距 35mm

风格要求：
- 低多边形简约风格
- 人物 = 拉伸立方体身体 + 球体头部
- 地面 = 平面
- 太阳光 + 补光

技术要求：
- 使用 EEVEE_NEXT 渲染引擎
- 材质必须同时设 diffuse_color 和 Principled BSDF 的 Base Color
- 渲染分辨率 1920x1080，24fps，72帧
- 输出路径：/Users/zengle/Documents/storyboard-3d-pipeline/render/test_glm_01.mp4
- 保存 .blend 文件到：/Users/zengle/Documents/storyboard-3d-pipeline/render/test_glm_01.blend
"""

# ============================================================
# System Prompt
# ============================================================
SYSTEM_PROMPT = """你是一个 Blender Python 专家。根据用户的分镜描述，生成完整的、可直接运行的 Blender Python 脚本。

要求：
1. 脚本必须以 `import bpy` 开头
2. 先清空场景（select_all + delete）
3. 创建材质时必须同时设置 diffuse_color（视口）和 Principled BSDF 的 Base Color（渲染）
4. 使用 BLENDER_EEVEE_NEXT 渲染引擎
5. 设置 World 环境光
6. 所有代码放在一个文件里，不需要外部依赖
7. 只输出 Python 代码，不要加 markdown 代码块标记，不要加解释文字
8. 代码末尾保存 .blend 文件
"""


# ============================================================
# 调用 GLM API 生成代码
# ============================================================
def generate_blender_code():
    """调用 GLM API 生成 Blender Python 代码"""
    import urllib.request
    import json

    url = f"{GLM_BASE_URL}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GLM_API_KEY}",
    }
    payload = {
        "model": GLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": SHOT_DESCRIPTION},
        ],
        "temperature": 0.7,
        "max_tokens": 4096,
    }

    print(f"正在调用 GLM API ({GLM_MODEL}) 生成 Blender 代码...")
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
            code = result["choices"][0]["message"]["content"]
            # 去掉可能的 markdown 代码块标记
            code = re.sub(r"^```python\s*", "", code)
            code = re.sub(r"```\s*$", "", code)
            print(f"✓ 代码生成成功，长度: {len(code)} 字符")
            return code
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        print(f"✗ API 调用失败: HTTP {e.code}")
        print(f"  响应: {error_body[:500]}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ 请求异常: {e}")
        sys.exit(1)


# ============================================================
# 渲染
# ============================================================
def render_with_blender(script_path):
    """调用 Blender 无头渲染"""
    print(f"开始渲染: {script_path}")
    result = subprocess.run(
        ["blender", "--background", "--python", str(script_path)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        print(f"✗ 渲染失败 (exit code {result.returncode})")
        print(f"  stderr: {result.stderr[-500:]}")
        return False
    else:
        # 检查输出文件是否存在
        mp4_path = RENDER_DIR / "test_glm_01.mp4"
        if mp4_path.exists():
            size = mp4_path.stat().st_size
            print(f"✓ 渲染成功: {mp4_path} ({size} bytes)")
            return True
        else:
            print("✗ 渲染完成但未找到输出文件")
            return False


# ============================================================
# 主流程
# ============================================================
if __name__ == "__main__":
    # 1. 生成代码
    code = generate_blender_code()

    # 2. 保存代码
    script_path = SHOTS_DIR / "test_glm_01_generated.py"
    script_path.write_text(code)
    print(f"✓ 代码已保存: {script_path}")

    # 3. 渲染
    print("\n" + "=" * 50)
    print("开始 Blender 渲染")
    print("=" * 50)
    success = render_with_blender(script_path)

    if success:
        print("\n✅ 全流程完成！")
        print(f"   视频路径: {RENDER_DIR / 'test_glm_01.mp4'}")
        print(f"   工程文件: {RENDER_DIR / 'test_glm_01.blend'}")
        print(f"   生成的代码: {script_path}")
    else:
        print("\n❌ 渲染失败，请检查生成的代码")
        print(f"   代码路径: {script_path}")
