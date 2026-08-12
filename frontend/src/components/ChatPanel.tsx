import { useEffect, useRef, useState } from 'react';
import { useStore } from '../store';
import styles from './ChatPanel.module.css';

interface ChatMessage {
  id: number;
  role: 'user' | 'agent' | 'tool' | 'status';
  content: string;
  kind?: 'error' | 'success' | 'info';
}

interface GenerateStatusResponse {
  status: string;
  error?: string;
  shot?: {
    export_hash: string;
    gltf_output_url: string;
    cameras: { camera_name: string }[];
    duration_seconds: number;
    frames_per_second: number;
  };
}

interface ChatPanelProperties {
  onBack: () => void;
}

/** V2 AI 生成聊天面板：输入描述 → SSE 流式显示过程 → 完成自动加载场景。 */
export function ChatPanel({ onBack }: ChatPanelProperties) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [description, setDescription] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [retryDescription, setRetryDescription] = useState<string | null>(null);
  const eventSourceReference = useRef<EventSource | null>(null);
  const messagesEndReference = useRef<HTMLDivElement | null>(null);
  const nextMessageId = useRef(1);
  const lastPromptReference = useRef<string | null>(null);
  const isGeneratingReference = useRef(false);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndReference.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Cleanup on unmount
  useEffect(() => {
    return () => eventSourceReference.current?.close();
  }, []);

  const appendMessage = (message: Omit<ChatMessage, 'id'>) => {
    setMessages((current) => [...current, { ...message, id: nextMessageId.current++ }]);
  };

  const loadShotIntoViewer = (shot: GenerateStatusResponse['shot']) => {
    if (!shot) return;
    useStore.setState({
      shot: {
        export_hash: shot.export_hash,
        gltf_output_url: shot.gltf_output_url,
        cameras: shot.cameras,
        animations: [],
        duration_seconds: shot.duration_seconds,
        frames_per_second: shot.frames_per_second,
      },
      activeCameraName: shot.cameras.length > 0 ? shot.cameras[0].camera_name : null,
      durationSeconds: shot.duration_seconds,
      framesPerSecond: shot.frames_per_second,
      currentTime: 0,
      isPlaying: false,
      isLoading: false,
      errorMessage: null,
    });
  };

  const finishGeneration = async (taskId: string) => {
    // 查询最终状态（done 携带 shot 元数据 / failed 携带错误）
    const response = await fetch(`/api/generate/${taskId}`);
    const data: GenerateStatusResponse = response.ok
      ? await response.json()
      : { status: 'failed', error: '无法查询任务状态' };

    if (data.status === 'done' && data.shot) {
      loadShotIntoViewer(data.shot);
      appendMessage({ role: 'status', kind: 'success', content: '✅ 生成完成，场景已加载' });
    } else if (data.status === 'cancelled') {
      appendMessage({ role: 'status', kind: 'info', content: '已取消生成' });
    } else {
      appendMessage({
        role: 'status',
        kind: 'error',
        content: `❌ 生成失败：${data.error || '未知错误'}`,
      });
      setRetryDescription(lastPromptReference.current);
    }
    isGeneratingReference.current = false;
    setIsGenerating(false);
    setActiveTaskId(null);
  };

  const handleSubmit = async (text?: string) => {
    const prompt = (text ?? description).trim();
    if (!prompt || isGenerating) return;

    appendMessage({ role: 'user', content: prompt });
    setDescription('');
    setRetryDescription(null);
    lastPromptReference.current = prompt;
    isGeneratingReference.current = true;
    setIsGenerating(true);

    try {
      const response = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: prompt }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `提交失败 (${response.status})`);
      }
      const { task_id } = await response.json();
      setActiveTaskId(task_id);

      const source = new EventSource(`/api/generate/${task_id}/stream`);
      eventSourceReference.current = source;
      source.onmessage = (event) => {
        let data: { type: string; content: string };
        try {
          data = JSON.parse(event.data);
        } catch {
          return;
        }
        if (data.type === 'text' && data.content) {
          appendMessage({ role: 'agent', content: data.content });
        } else if (data.type === 'tool' && data.content) {
          appendMessage({ role: 'tool', content: data.content });
        } else if (data.type === 'status') {
          source.close();
          eventSourceReference.current = null;
          void finishGeneration(task_id);
        }
      };
      source.onerror = () => {
        source.close();
        eventSourceReference.current = null;
        // 流意外断开（可能任务已结束但 status 事件丢失）——查询最终状态收尾
        if (isGeneratingReference.current) {
          void finishGeneration(task_id);
        }
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误';
      appendMessage({ role: 'status', kind: 'error', content: `❌ ${message}` });
      isGeneratingReference.current = false;
      setIsGenerating(false);
    }
  };

  const handleStop = async () => {
    if (!activeTaskId) return;
    try {
      await fetch(`/api/generate/${activeTaskId}/stop`, { method: 'POST' });
    } catch {
      // stop is best-effort; the SSE disconnect below also interrupts
    }
    eventSourceReference.current?.close();
    eventSourceReference.current = null;
    appendMessage({ role: 'status', kind: 'info', content: '已发送停止请求…' });
    isGeneratingReference.current = false;
    setIsGenerating(false);
    setActiveTaskId(null);
  };

  const handleRetry = () => {
    if (retryDescription) {
      void handleSubmit(retryDescription);
    }
  };

  return (
    <div className={styles.chatPanel}>
      <div className={styles.chatHeader}>
        <button className={styles.backButton} onClick={onBack} title="返回">
          ←
        </button>
        <span className={styles.chatTitle}>AI 生成</span>
      </div>

      <div className={styles.messageList}>
        {messages.length === 0 && (
          <div className={styles.emptyHint}>
            描述一个场景，例如：
            <br />
            “两个人在咖啡店对话，一个男人正脸镜头，一个女人背影镜头”
          </div>
        )}
        {messages.map((message) => (
          <div key={message.id} className={styles[`message_${message.role}`]}>
            {message.role === 'tool' ? (
              <pre className={styles.toolBlock}>{message.content}</pre>
            ) : (
              <span
                className={
                  message.kind === 'error'
                    ? styles.messageError
                    : message.kind === 'success'
                      ? styles.messageSuccess
                      : message.kind === 'info'
                        ? styles.messageInfo
                        : undefined
                }
              >
                {message.content}
              </span>
            )}
          </div>
        ))}
        {isGenerating && (
          <div className={styles.generatingIndicator}>
            <span className={styles.spinner} />
            正在生成…
          </div>
        )}
        <div ref={messagesEndReference} />
      </div>

      {!isGenerating && (
        <div className={styles.inputArea}>
          <textarea
            className={styles.input}
            placeholder="输入场景描述…"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                void handleSubmit();
              }
            }}
            rows={3}
          />
          <div className={styles.inputActions}>
            {retryDescription && (
              <button className={styles.retryButton} onClick={handleRetry}>
                重试上次
              </button>
            )}
            <button
              className={styles.submitButton}
              onClick={() => void handleSubmit()}
              disabled={!description.trim()}
            >
              生成
            </button>
          </div>
        </div>
      )}

      {isGenerating && (
        <div className={styles.stopArea}>
          <button className={styles.stopButton} onClick={() => void handleStop()}>
            ■ 停止生成
          </button>
        </div>
      )}
    </div>
  );
}
