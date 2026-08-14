import { useEffect, useRef, useState } from 'react';
import { useStore } from '../store';
import styles from './ChatPanel.module.css';

interface ChatMessage {
  id: number;
  role: 'user' | 'agent' | 'tool_start' | 'tool_end' | 'tool_output' | 'status';
  content: string;
  name?: string;
  duration?: number;
  kind?: 'error' | 'success' | 'info';
}

interface GenerateStatusResponse {
  status: string;
  error?: string;
  shot?: {
    export_hash: string;
    gltf_output_url: string;
    cameras: { camera_name: string }[];
    animations: { animation_name: string; animation_length_seconds: number }[];
    duration_seconds: number;
    frames_per_second: number;
    frame_aspect?: number;
  };
}

/** AI generation chat panel: describe a scene → live SSE log → auto-load the result. */
export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [description, setDescription] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [retryDescription, setRetryDescription] = useState<string | null>(null);
  const [waitingModel, setWaitingModel] = useState(false);
  const eventSourceReference = useRef<EventSource | null>(null);
  const messagesEndReference = useRef<HTMLDivElement | null>(null);
  const nextMessageId = useRef(1);
  const lastPromptReference = useRef<string | null>(null);
  const isGeneratingReference = useRef(false);
  const lastToolStartTime = useRef<number | null>(null);

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
        animations: shot.animations ?? [],
        duration_seconds: shot.duration_seconds,
        frames_per_second: shot.frames_per_second,
        frame_aspect: shot.frame_aspect,
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
    // Fetch the final status (done carries shot metadata / failed carries the error)
    const response = await fetch(`/api/generate/${taskId}`);
    const data: GenerateStatusResponse = response.ok
      ? await response.json()
      : { status: 'failed', error: 'Failed to query task status' };

    if (data.status === 'done' && data.shot) {
      loadShotIntoViewer(data.shot);
      appendMessage({ role: 'status', kind: 'success', content: '✅ Generation complete, scene loaded' });
    } else if (data.status === 'cancelled') {
      appendMessage({ role: 'status', kind: 'info', content: 'Generation cancelled' });
    } else {
      appendMessage({
        role: 'status',
        kind: 'error',
        content: `❌ Generation failed: ${data.error || 'Unknown error'}`,
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
        throw new Error(errorData.detail || `Submit failed (${response.status})`);
      }
      const { task_id } = await response.json();
      setActiveTaskId(task_id);

      const source = new EventSource(`/api/generate/${task_id}/stream`);
      eventSourceReference.current = source;
      setWaitingModel(true); // covers the initial model-thinking gap
      source.onmessage = (event) => {
        let data: {
          type: string;
          content?: string;
          name?: string;
          arguments?: string;
          usage?: { input_tokens: number; output_tokens: number; total_tokens: number };
        };
        try {
          data = JSON.parse(event.data);
        } catch {
          return;
        }
        setWaitingModel(false);
        // Defensive: some payloads carry objects instead of strings
        const toText = (value: unknown): string =>
          typeof value === 'string' ? value : JSON.stringify(value);
        if (data.type === 'text' && data.content) {
          appendMessage({ role: 'agent', content: toText(data.content) });
          // After agent text, the next thing is usually a tool call or done —
          // show the waiting hint again until the next event arrives.
          setWaitingModel(true);
        } else if (data.type === 'tool_start') {
          lastToolStartTime.current = Date.now();
          appendMessage({
            role: 'tool_start',
            name: data.name ?? 'tool',
            content: toText(data.arguments ?? '').slice(0, 120),
          });
        } else if (data.type === 'tool_end') {
          const duration =
            lastToolStartTime.current !== null
              ? Math.max(0, (Date.now() - lastToolStartTime.current) / 1000)
              : undefined;
          appendMessage({
            role: 'tool_end',
            name: data.name ?? 'tool',
            content: '',
            duration,
          });
          setWaitingModel(true); // model is thinking about the tool result
        } else if (data.type === 'tool_output' && data.content) {
          appendMessage({ role: 'tool_output', content: toText(data.content).slice(0, 150) });
        } else if (data.type === 'status') {
          setWaitingModel(false);
          if (data.usage) {
            const usage = data.usage as { input_tokens: number; output_tokens: number; total_tokens: number };
            appendMessage({
              role: 'status',
              kind: 'info',
              content: `Tokens — input: ${usage.input_tokens.toLocaleString()}, output: ${usage.output_tokens.toLocaleString()}, total: ${usage.total_tokens.toLocaleString()}`,
            });
          }
          source.close();
          eventSourceReference.current = null;
          void finishGeneration(task_id);
        }
      };
      source.onerror = () => {
        source.close();
        eventSourceReference.current = null;
        // Stream dropped (the task may have finished without a status event) —
        // query the final status to wrap up.
        if (isGeneratingReference.current) {
          void finishGeneration(task_id);
        }
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
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
    appendMessage({ role: 'status', kind: 'info', content: 'Stop requested…' });
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
        <span className={styles.chatTitle}>AI Generate</span>
      </div>

      <div className={styles.messageList}>
        {messages.length === 0 && (
          <div className={styles.emptyHint}>
            Describe a scene, e.g.
            <br />
            “Two people talking in a coffee shop — one man head-on shot, one woman
            back shot”
          </div>
        )}
        {messages.map((message) => (
          <div key={message.id} className={styles[`message_${message.role}`]}>
            {message.role === 'tool_start' && (
              <div className={styles.toolCallBlock}>
                <span className={styles.toolCallHeader}>
                  🔧 {message.name}
                </span>
                <span className={styles.toolCallArgs}>{message.content}</span>
              </div>
            )}
            {message.role === 'tool_end' && (
              <span className={styles.toolDoneLine}>
                ✓ {message.name}
                {message.duration !== undefined && (
                  <span className={styles.toolDuration}>
                    ({message.duration.toFixed(1)}s)
                  </span>
                )}
              </span>
            )}
            {message.role === 'tool_output' && (
              <pre className={styles.toolOutputBlock}>
                {message.content}
                {message.content.length >= 150 ? '…' : ''}
              </pre>
            )}
            {message.role === 'user' && (
              <span className={styles.messageUserText}>{message.content}</span>
            )}
            {message.role === 'agent' && <span>{message.content}</span>}
            {message.role === 'status' && (
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
            {waitingModel ? 'Waiting for model response…' : 'Generating…'}
          </div>
        )}
        <div ref={messagesEndReference} />
      </div>

      {!isGenerating && (
        <div className={styles.inputArea}>
          <textarea
            className={styles.input}
            placeholder="Describe a scene…"
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
                Retry last
              </button>
            )}
            <button
              className={styles.submitButton}
              onClick={() => void handleSubmit()}
              disabled={!description.trim()}
            >
              Generate
            </button>
          </div>
        </div>
      )}

      {isGenerating && (
        <div className={styles.stopArea}>
          <button className={styles.stopButton} onClick={() => void handleStop()}>
            ■ Stop
          </button>
        </div>
      )}
    </div>
  );
}
