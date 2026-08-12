"""V2 设置接口测试 — DeepSeek key 验证 / 配置读写 / agent 重启（全部 mock，不触真实服务）。"""
import json

import pytest
from fastapi.testclient import TestClient

from backend import agent_service, settings
from backend.main import application

client = TestClient(application)


@pytest.fixture(autouse=True)
def isolate_settings_paths(monkeypatch, tmp_path):
    """隔离 HERMES_HOME 路径，避免污染项目真实配置。"""
    fake_home = tmp_path / "hermes-home"
    fake_home.mkdir()
    monkeypatch.setattr(settings, "HERMES_HOME", fake_home)
    monkeypatch.setattr(settings, "ENV_FILE", fake_home / ".env")
    monkeypatch.setattr(settings, "CONFIG_FILE", fake_home / "config.yaml")


def test_get_settings_defaults_when_unconfigured(monkeypatch):
    """未配置任何内容时：返回默认值且 key_configured=False。"""
    monkeypatch.setattr(agent_service, "is_agent_running", lambda: True)

    response = client.get("/api/settings")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "deepseek"
    assert body["key_configured"] is False
    assert body["agent_running"] is True


def test_get_settings_reads_existing_configuration(monkeypatch, tmp_path):
    """已配置后：读取现有模型/推理级别/key 状态。"""
    fake_home = tmp_path / "hermes-home"
    (fake_home / ".env").write_text("API_SERVER_KEY=abc123\nDEEPSEEK_API_KEY=sk-existing\n")
    (fake_home / "config.yaml").write_text(
        "model:\n  base_url: https://api.deepseek.com/v1\n"
        "  default: deepseek-v4-pro\n  provider: deepseek\n"
        "agent:\n  reasoning_overrides:\n    deepseek-v4-pro: max\n"
    )
    monkeypatch.setattr(agent_service, "is_agent_running", lambda: False)

    response = client.get("/api/settings")

    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "deepseek-v4-pro"
    assert body["reasoning_level"] == "max"
    assert body["key_configured"] is True
    assert body["agent_running"] is False


def test_post_settings_with_valid_key_saves_and_restarts(monkeypatch, tmp_path):
    """key 验证通过：写入 .env + config.yaml，并触发 agent 重启。"""
    monkeypatch.setattr(settings, "validate_deepseek_key", lambda key: key == "sk-good")
    restarted = []
    monkeypatch.setattr(agent_service, "restart_agent", lambda: restarted.append(True) or {"ok": True})
    fake_home = tmp_path / "hermes-home"

    response = client.post(
        "/api/settings",
        json={
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "reasoning_level": "high",
            "api_key": "sk-good",
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert restarted == [True]
    # key 写入 .env
    env_content = (fake_home / ".env").read_text()
    assert "DEEPSEEK_API_KEY=sk-good" in env_content
    # 模型与推理级别写入 config.yaml
    config_content = (fake_home / "config.yaml").read_text()
    assert "deepseek-v4-flash" in config_content
    assert "high" in config_content


def test_post_settings_with_invalid_key_rejects(monkeypatch, tmp_path):
    """key 验证失败：400 错误，不写文件、不重启。"""
    monkeypatch.setattr(settings, "validate_deepseek_key", lambda key: False)
    restarted = []
    monkeypatch.setattr(agent_service, "restart_agent", lambda: restarted.append(True))

    response = client.post(
        "/api/settings",
        json={
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "reasoning_level": "high",
            "api_key": "sk-bad",
        },
    )

    assert response.status_code == 400
    assert "无效" in response.json()["detail"]
    assert restarted == []
    assert not (tmp_path / "hermes-home" / ".env").exists()


def test_post_settings_without_key_keeps_existing(monkeypatch, tmp_path):
    """不传 api_key：保留现有 key，只更新模型/推理级别。"""
    monkeypatch.setattr(settings, "validate_deepseek_key", lambda key: True)
    fake_home = tmp_path / "hermes-home"
    (fake_home / ".env").write_text("API_SERVER_KEY=abc123\nDEEPSEEK_API_KEY=sk-old\n")

    response = client.post(
        "/api/settings",
        json={
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "reasoning_level": "max",
        },
    )

    assert response.status_code == 200
    env_content = (fake_home / ".env").read_text()
    assert "DEEPSEEK_API_KEY=sk-old" in env_content


def test_post_settings_rejects_unknown_model(monkeypatch):
    """不支持的模型：422 校验错误。"""
    monkeypatch.setattr(settings, "validate_deepseek_key", lambda key: True)

    response = client.post(
        "/api/settings",
        json={
            "provider": "deepseek",
            "model": "deepseek-v9-ultra",
            "reasoning_level": "high",
            "api_key": "sk-good",
        },
    )

    assert response.status_code == 422
