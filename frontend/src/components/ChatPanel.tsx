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

/** AI generation chat panel: describe a scene → live SSE log → auto-load the result. */
export function ChatPanel() {
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
            Generating…
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
