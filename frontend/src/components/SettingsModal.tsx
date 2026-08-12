import { useEffect, useState } from 'react';
import styles from './SettingsModal.module.css';

interface SettingsModalProperties {
  onClose: () => void;
}

interface SettingsResponse {
  provider: string;
  model: string;
  reasoning_level: string;
  key_configured: boolean;
  agent_running: boolean;
}

const MODEL_OPTIONS = ['deepseek-v4-flash', 'deepseek-v4-pro'];
const REASONING_OPTIONS = ['low', 'high', 'max'];

/** V2 settings modal: DeepSeek provider / model / reasoning level / API key. */
export function SettingsModal({ onClose }: SettingsModalProperties) {
  const [model, setModel] = useState('deepseek-v4-flash');
  const [reasoningLevel, setReasoningLevel] = useState('high');
  const [apiKey, setApiKey] = useState('');
  const [keyConfigured, setKeyConfigured] = useState(false);
  const [agentRunning, setAgentRunning] = useState(false);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; text: string } | null>(null);

  // Load current settings on open
  useEffect(() => {
    fetch('/api/settings')
      .then((response) => response.json())
      .then((data: SettingsResponse) => {
        setModel(data.model);
        setReasoningLevel(data.reasoning_level);
        setKeyConfigured(data.key_configured);
        setAgentRunning(data.agent_running);
      })
      .catch(() => setFeedback({ ok: false, text: '无法读取当前设置' }));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setFeedback(null);
    try {
      const payload: Record<string, string> = {
        provider: 'deepseek',
        model,
        reasoning_level: reasoningLevel,
      };
      if (apiKey.trim()) {
        payload.api_key = apiKey.trim();
      }

      const response = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || `保存失败 (${response.status})`);
      }
      setApiKey('');
      setKeyConfigured(true);
      setFeedback({ ok: true, text: '设置已保存，Agent 服务已重启' });
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误';
      setFeedback({ ok: false, text: message });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(event) => event.stopPropagation()}>
        <div className={styles.header}>
          <span className={styles.title}>API 设置</span>
          <button className={styles.closeButton} onClick={onClose} aria-label="关闭">
            ✕
          </button>
        </div>

        <div className={styles.body}>
          <label className={styles.field}>
            <span className={styles.label}>Provider</span>
            <input className={styles.input} value="DeepSeek" disabled />
          </label>

          <label className={styles.field}>
            <span className={styles.label}>模型</span>
            <select
              className={styles.input}
              value={model}
              onChange={(event) => setModel(event.target.value)}
            >
              {MODEL_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>

          <label className={styles.field}>
            <span className={styles.label}>推理级别</span>
            <select
              className={styles.input}
              value={reasoningLevel}
              onChange={(event) => setReasoningLevel(event.target.value)}
            >
              {REASONING_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>

          <label className={styles.field}>
            <span className={styles.label}>
              API Key
              {keyConfigured && <span className={styles.configuredBadge}>已配置</span>}
            </span>
            <input
              className={styles.input}
              type="password"
              placeholder={keyConfigured ? '已配置（输入新 key 可更换）' : '输入 DeepSeek API key'}
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
            />
          </label>

          {!agentRunning && (
            <div className={styles.warning}>⚠ Agent 服务未运行，AI 生成不可用</div>
          )}

          {feedback && (
            <div className={feedback.ok ? styles.feedbackOk : styles.feedbackError}>
              {feedback.text}
            </div>
          )}
        </div>

        <div className={styles.footer}>
          <button className={styles.cancelButton} onClick={onClose}>
            取消
          </button>
          <button className={styles.saveButton} onClick={handleSave} disabled={saving}>
            {saving ? '保存中…' : '保存'}
          </button>
        </div>
      </div>
    </div>
  );
}
