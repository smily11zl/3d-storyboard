"""Hermes API Server 客户端 — 健康检查、重启、生成任务提交（切片 03 扩展）。"""
import os
import signal
import subprocess
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HERMES_HOME = PROJECT_ROOT / ".hermes-home"
AGENT_PORT = int(os.environ.get("AGENT_PORT", "8643"))
AGENT_BASE_URL = f"http://127.0.0.1:{AGENT_PORT}"
VENV_HERMES_BINARY = PROJECT_ROOT / ".venv" / "bin" / "hermes"

AGENT_STARTUP_TIMEOUT_SECONDS = 20
AGENT_HEALTH_TIMEOUT_SECONDS = 2

# 与本机 launchd 版 Hermes 共享的环境变量可能污染平台检测
# （WEIXIN_* 等），启动 agent 时用干净环境（与 start.sh 保持一致）
_AGENT_ENV_PREFIX = {
    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/Applications/Blender.app/Contents/MacOS",
    "HOME": str(Path.home()),
    "HERMES_HOME": str(HERMES_HOME),
    "LANG": os.environ.get("LANG", "en_US.UTF-8"),
}


def get_api_server_key() -> str:
    """从项目 .hermes-home/.env 读取 API_SERVER_KEY。"""
    env_file = HERMES_HOME / ".env"
    if not env_file.exists():
        return ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("API_SERVER_KEY="):
            return line.split("=", 1)[1].strip()
    return ""


def is_agent_running() -> bool:
    """健康检查：GET /health 返回 200 即视为运行中。"""
    import httpx

    try:
        response = httpx.get(f"{AGENT_BASE_URL}/health", timeout=AGENT_HEALTH_TIMEOUT_SECONDS)
        return response.status_code == 200
    except Exception:
        return False


def _kill_agent_on_port() -> None:
    """杀掉占用 agent 端口的进程（lsof + kill）。"""
    try:
        output = subprocess.run(
            ["lsof", "-ti", f"tcp:{AGENT_PORT}"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        if output:
            for pid in output.splitlines():
                subprocess.run(["kill", "-9", pid], timeout=5)
    except Exception:
        pass


def _start_agent_process() -> subprocess.Popen:
    """用干净环境拉起 agent gateway（与 start.sh 的 env -i 逻辑一致）。"""
    return subprocess.Popen(
        [str(VENV_HERMES_BINARY), "gateway", "run", "--force"],
        cwd=str(PROJECT_ROOT),
        env=_AGENT_ENV_PREFIX,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def restart_agent() -> dict:
    """重启 agent：杀掉现有进程 → 拉起新进程 → 等待健康检查通过。

    返回 {"ok": bool, "message": str}。
    """
    _kill_agent_on_port()
    process = _start_agent_process()

    deadline = time.monotonic() + AGENT_STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if is_agent_running():
            return {"ok": True, "message": f"Agent API server restarted (PID {process.pid})"}
        time.sleep(1)

    return {"ok": False, "message": "Agent API server did not become healthy in time"}


def stop_agent() -> dict:
    """停止 agent：杀掉端口进程。返回 {"ok": bool, "message": str}。"""
    _kill_agent_on_port()
    return {"ok": not is_agent_running(), "message": "Agent API server stopped"}
