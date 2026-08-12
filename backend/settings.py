"""V2 设置接口 — DeepSeek provider/模型/推理级别/API key 配置。"""
import os
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend import agent_service

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HERMES_HOME = PROJECT_ROOT / ".hermes-home"
ENV_FILE = HERMES_HOME / ".env"
CONFIG_FILE = HERMES_HOME / "config.yaml"

DEEPSEEK_MODELS_ENDPOINT = "https://api.deepseek.com/v1/models"
ALLOWED_MODELS = ["deepseek-v4-flash", "deepseek-v4-pro"]
ALLOWED_REASONING_LEVELS = ["low", "high", "max"]
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_REASONING_LEVEL = "high"

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsPayload(BaseModel):
    provider: str = "deepseek"
    model: str
    reasoning_level: str
    api_key: str | None = None


def validate_deepseek_key(api_key: str) -> bool:
    """直接调 DeepSeek 官方接口验证 key 有效性（200 = 有效）。"""
    import httpx

    try:
        response = httpx.get(
            DEEPSEEK_MODELS_ENDPOINT,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        return response.status_code == 200
    except Exception:
        return False


def _read_env_value(key_name: str) -> str:
    """从 .env 读取变量值（无文件/无变量返回空串）。"""
    if not ENV_FILE.exists():
        return ""
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key_name}="):
            return line.split("=", 1)[1].strip()
    return ""


def _write_env_value(key_name: str, value: str) -> None:
    """写入/更新 .env 变量（保留其他行）。"""
    lines = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    replaced = False
    for index, line in enumerate(lines):
        if line.startswith(f"{key_name}="):
            lines[index] = f"{key_name}={value}"
            replaced = True
    if not replaced:
        lines.append(f"{key_name}={value}")
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_config_yaml() -> dict:
    """读取 config.yaml（不存在返回空 dict）。"""
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE, encoding="utf-8") as file_handle:
        return yaml.safe_load(file_handle) or {}


def _write_config_yaml(config_data: dict) -> None:
    """写回 config.yaml（保留原有字段）。"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as file_handle:
        yaml.safe_dump(config_data, file_handle, allow_unicode=True, sort_keys=False)


def read_current_settings() -> dict:
    """读取当前配置：模型/推理级别来自 config.yaml，key 状态来自 .env。"""
    config_data = _read_config_yaml()
    model = config_data.get("model", {}).get("default", DEFAULT_MODEL)
    reasoning_overrides = config_data.get("agent", {}).get("reasoning_overrides", {})
    reasoning_level = reasoning_overrides.get(model, DEFAULT_REASONING_LEVEL)

    return {
        "provider": "deepseek",
        "model": model,
        "reasoning_level": reasoning_level,
        "key_configured": bool(_read_env_value("DEEPSEEK_API_KEY")),
        "agent_running": agent_service.is_agent_running(),
    }


@router.get("")
def get_settings() -> dict:
    """获取当前设置（key 只返回是否已配置，不返回明文）。"""
    return read_current_settings()


@router.post("")
def save_settings(payload: SettingsPayload) -> dict:
    """保存设置：验证 key → 写 .env + config.yaml → 重启 agent。"""
    if payload.model not in ALLOWED_MODELS:
        raise HTTPException(status_code=422, detail=f"不支持的模型: {payload.model}")
    if payload.reasoning_level not in ALLOWED_REASONING_LEVELS:
        raise HTTPException(
            status_code=422, detail=f"不支持的推理级别: {payload.reasoning_level}"
        )

    if payload.api_key:
        if not validate_deepseek_key(payload.api_key):
            raise HTTPException(status_code=400, detail="API key 无效，请检查后重试")
        _write_env_value("DEEPSEEK_API_KEY", payload.api_key)

    config_data = _read_config_yaml()
    config_data.setdefault("model", {})["default"] = payload.model
    config_data.setdefault("model", {})["provider"] = payload.provider
    config_data.setdefault("agent", {}).setdefault("reasoning_overrides", {})[
        payload.model
    ] = payload.reasoning_level
    _write_config_yaml(config_data)

    restart_result = agent_service.restart_agent()

    return {
        "ok": True,
        "message": "设置已保存" + ("，Agent 服务已重启" if restart_result["ok"] else "，但 Agent 重启失败"),
        "agent_restart_ok": restart_result["ok"],
    }
