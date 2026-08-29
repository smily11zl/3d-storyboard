import { useEffect, useRef, useState } from 'react';
import { useStore } from '../store';
import styles from './SegmentSidebar.module.css';

const RAD_TO_DEG = 180 / Math.PI;
const DEG_TO_RAD = Math.PI / 180;

interface NumberFieldProperties {
  label: string;
  value: number;
  step: number;
  onChange: (value: number) => void;
}

/** 受控数值输入框：支持负号/小数点中间态，实时去前导零，非法输入不提交、blur 时回退上次正确值。 */
function NumberField({ label, value, step, onChange }: NumberFieldProperties) {
  const [display, setDisplay] = useState<string>(String(Number(value.toFixed(3))));
  const [focused, setFocused] = useState(false);
  const committedRef = useRef<number>(value);

  // 外部 value 变化（非聚焦时）同步 display
  useEffect(() => {
    if (!focused) {
      setDisplay(String(Number(value.toFixed(3))));
      committedRef.current = value;
    }
  }, [value, focused]);

  // 实时去前导零：整数 "09" -> "9"（小数 "0.5" 的 0 是整数部分，不去）
  const stripLeadingZeros = (raw: string): string => {
    const trimmed = raw.trim();
    if (/^-?0\d+$/.test(trimmed)) {
      const negative = trimmed.startsWith('-');
      const digits = (negative ? trimmed.slice(1) : trimmed).replace(/^0+/, '');
      return (negative ? '-' : '') + (digits || '0');
    }
    return trimmed;
  };

  const handleChange = (raw: string) => {
    const current = stripLeadingZeros(raw);
    setDisplay(current);
    // 负号 / 小数点 / 空 / 末尾小数点 都是中间态，不提交；只有完整数值才提交
    const isIntermediate =
      current === '' || current === '-' || current === '.' || current === '-.' || current.endsWith('.');
    if (!isIntermediate) {
      const num = Number(current);
      if (Number.isFinite(num)) {
        console.log('[input-change]', current, '=>', num);
        committedRef.current = num;
        onChange(num);
      }
    }
  };

  const handleBlur = () => {
    setFocused(false);
    const trimmed = display.trim();
    const num = Number(trimmed);
    if (trimmed === '' || !Number.isFinite(num)) {
      console.log('[input-blur]', trimmed, '=> 回退', committedRef.current);
      // 非法 → 回退上次正确值
      setDisplay(String(Number(committedRef.current.toFixed(3))));
    } else {
      console.log('[input-blur]', trimmed, '=>', num);
      committedRef.current = num;
      onChange(num);
      setDisplay(String(Number(num.toFixed(3))));
    }
  };

  return (
    <label className={styles.field}>
      <span className={styles.fieldLabel}>{label}</span>
      <input
        type="text"
        inputMode="decimal"
        className={styles.fieldInput}
        value={display}
        step={step}
        onFocus={() => setFocused(true)}
        onChange={(event) => handleChange(event.target.value)}
        onBlur={handleBlur}
      />
    </label>
  );
}

/** 编辑态右侧侧栏：时长 / 位置+插值 / 朝向+模式切换（三段）。 */
export function SegmentSidebar() {
  const shot = useStore((state) => state.shot);
  const selectedSegment = useStore((state) => state.selectedSegment);
  const setSelectedSegment = useStore((state) => state.setSelectedSegment);
  const editingSegments = useStore((state) => state.editingSegments);
  const setSegmentPose = useStore((state) => state.setSegmentPose);
  const setSegmentTarget = useStore((state) => state.setSegmentTarget);
  const setOrientationMode = useStore((state) => state.setOrientationMode);
  const setInterpolation = useStore((state) => state.setInterpolation);
  const setCurrentTime = useStore((state) => state.setCurrentTime);
  const deleteSegment = useStore((state) => state.deleteSegment);
  const setSegmentDuration = useStore((state) => state.setSegmentDuration);

  if (!selectedSegment) return null;

  const segment = (editingSegments ?? shot?.segments)?.find(
    (candidate) =>
      candidate.camera_name === selectedSegment.camera_name &&
      candidate.segment_name === selectedSegment.segment_name,
  );

  if (!segment) return null;

  const isSimple = segment.segment_type === 'S';
  const key = `${segment.camera_name}:${segment.segment_name}`;

  const startPosition = segment.start_pose.position;
  const startRotation = segment.start_pose.rotation;
  const endPosition = segment.end_pose.position;
  const endRotation = segment.end_pose.rotation;
  const targetPosition = segment.target_position ?? null;
  const orientationMode =
    segment.orientation_mode ??
    (segment.constraint?.rotation?.length ? 'follow' : 'interpolate');
  const positionInterpolation = segment.interpolation?.position ?? 'LINEAR';
  const rotationInterpolation = segment.interpolation?.rotation ?? 'LINEAR';

  const updatePosition = (which: 'start' | 'end', index: number, value: number) => {
    const base = which === 'start' ? startPosition : endPosition;
    const rotation = which === 'start' ? startRotation : endRotation;
    const newPosition: [number, number, number] = [...base];
    newPosition[index] = value;
    setSegmentPose(key, which, newPosition, rotation);
  };

  const updateRotation = (which: 'start' | 'end', index: number, degrees: number) => {
    const position = which === 'start' ? startPosition : endPosition;
    const base = which === 'start' ? startRotation : endRotation;
    const newRotation: [number, number, number] = [...base];
    newRotation[index] = degrees * DEG_TO_RAD;
    setSegmentPose(key, which, position, newRotation);
  };

  const updateTarget = (index: number, value: number) => {
    const base = targetPosition ?? [0, 0, 0];
    const newTarget: [number, number, number] = [...base];
    newTarget[index] = value;
    setSegmentTarget(key, newTarget);
  };

  const renderInterpolationSelect = (channel: 'position' | 'rotation', value: string) => (
    <select
      className={styles.interpolationSelect}
      value={value}
      onChange={(event) => setInterpolation(key, channel, event.target.value)}
    >
      <option value="LINEAR">Linear</option>
      <option value="CONSTANT">Constant</option>
    </select>
  );

  const renderRotationRow = (which: 'start' | 'end') => {
    const rotation = which === 'start' ? startRotation : endRotation;
    return (
      <div className={styles.poseRow}>
        <span className={styles.poseRowLabel}>{which === 'start' ? 'Start' : 'End'}</span>
        <div className={styles.poseFields}>
          <NumberField
            label="RX"
            value={rotation[0] * RAD_TO_DEG}
            step={1}
            onChange={(value) => updateRotation(which, 0, value)}
          />
          <NumberField
            label="RY"
            value={rotation[1] * RAD_TO_DEG}
            step={1}
            onChange={(value) => updateRotation(which, 1, value)}
          />
          <NumberField
            label="RZ"
            value={rotation[2] * RAD_TO_DEG}
            step={1}
            onChange={(value) => updateRotation(which, 2, value)}
          />
        </div>
      </div>
    );
  };

  return (
    <aside className={styles.sidebar}>
      <div className={styles.header}>
        <span className={styles.title}>{segment.segment_name}</span>
        <button
          className={styles.closeButton}
          onClick={() => setSelectedSegment(null)}
          title="Close"
          aria-label="Close sidebar"
        >
          ✕
        </button>
      </div>
      <div className={styles.body}>
        <div className={styles.meta}>
          <span className={styles.cameraName}>{segment.camera_name}</span>
          <span className={`${styles.typeBadge} ${isSimple ? styles.typeSimple : styles.typeComplex}`}>
            {isSimple ? 'Simple' : 'Complex'}
          </span>
        </div>

        {isSimple ? (
          <>
            {/* 1. 时长 */}
            <div className={styles.section}>
              <div className={styles.sectionTitle}>Duration</div>
              <div className={styles.timeRow}>
                <span>Start</span>
                <button
                  className={styles.frameButton}
                  onClick={() => setCurrentTime(segment.start_time)}
                  title="Jump playhead to start"
                >
                  {segment.start_time.toFixed(2)}s
                </button>
              </div>
              <div className={styles.timeRow}>
                <span>End</span>
                <input
                  type="number"
                  className={styles.fieldInput}
                  value={Number(segment.end_time.toFixed(2))}
                  step={0.1}
                  onChange={(event) =>
                    setSegmentDuration(
                      segment.camera_name,
                      segment.segment_name,
                      parseFloat(event.target.value) || 0,
                    )
                  }
                />
              </div>
            </div>

            {/* 2. 位置 */}
            <div className={styles.section}>
              <div className={styles.sectionTitle}>Position</div>
              <div className={styles.interpolationRow}>
                <span className={styles.interpolationLabel}>Interpolation</span>
                {renderInterpolationSelect('position', positionInterpolation)}
              </div>
              <div className={styles.poseRow}>
                <span className={styles.poseRowLabel}>Start</span>
                <div className={styles.poseFields}>
                  <NumberField label="X" value={startPosition[0]} step={0.1} onChange={(value) => updatePosition('start', 0, value)} />
                  <NumberField label="Y" value={startPosition[1]} step={0.1} onChange={(value) => updatePosition('start', 1, value)} />
                  <NumberField label="Z" value={startPosition[2]} step={0.1} onChange={(value) => updatePosition('start', 2, value)} />
                </div>
              </div>
              <div className={styles.poseRow}>
                <span className={styles.poseRowLabel}>End</span>
                <div className={styles.poseFields}>
                  <NumberField label="X" value={endPosition[0]} step={0.1} onChange={(value) => updatePosition('end', 0, value)} />
                  <NumberField label="Y" value={endPosition[1]} step={0.1} onChange={(value) => updatePosition('end', 1, value)} />
                  <NumberField label="Z" value={endPosition[2]} step={0.1} onChange={(value) => updatePosition('end', 2, value)} />
                </div>
              </div>
            </div>

            {/* 3. 朝向 */}
            <div className={styles.section}>
              <div className={styles.sectionTitle}>Orientation</div>
              <div className={styles.modeToggle}>
                <button
                  className={`${styles.modeToggleButton} ${orientationMode === 'interpolate' ? styles.modeToggleActive : ''}`}
                  onClick={() => setOrientationMode(key, 'interpolate')}
                >
                  Interpolate
                </button>
                <button
                  className={`${styles.modeToggleButton} ${orientationMode === 'follow' ? styles.modeToggleActive : ''}`}
                  onClick={() => setOrientationMode(key, 'follow')}
                >
                  Follow
                </button>
              </div>
              {orientationMode === 'interpolate' ? (
                <>
                  <div className={styles.interpolationRow}>
                    <span className={styles.interpolationLabel}>Interpolation</span>
                    {renderInterpolationSelect('rotation', rotationInterpolation)}
                  </div>
                  {renderRotationRow('start')}
                  {renderRotationRow('end')}
                </>
              ) : (
                <div className={styles.poseRow}>
                  <span className={styles.poseRowLabel}>Target</span>
                  <div className={styles.poseFields}>
                    <NumberField label="TX" value={(targetPosition ?? [0, 0, 0])[0]} step={0.1} onChange={(value) => updateTarget(0, value)} />
                    <NumberField label="TY" value={(targetPosition ?? [0, 0, 0])[1]} step={0.1} onChange={(value) => updateTarget(1, value)} />
                    <NumberField label="TZ" value={(targetPosition ?? [0, 0, 0])[2]} step={0.1} onChange={(value) => updateTarget(2, value)} />
                  </div>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className={styles.complexNotice}>
            <span className={styles.complexNoticeText}>Complex segment — cannot edit</span>
          </div>
        )}

        <button
          className={styles.deleteButton}
          onClick={() => {
            if (window.confirm(`Delete segment "${segment.segment_name}"?`)) {
              deleteSegment(segment.camera_name, segment.segment_name);
            }
          }}
          title="Delete segment"
        >
          Delete
        </button>
      </div>
    </aside>
  );
}
