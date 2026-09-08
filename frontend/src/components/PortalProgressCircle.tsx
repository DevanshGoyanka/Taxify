import React, { useEffect, useRef, useState } from 'react';

export type PortalProgressPhase = 'signing_in' | 'downloading' | 'complete' | 'failed';

interface PortalProgressCircleProps {
  phase: PortalProgressPhase;
  size?: number;
  color?: string;
  trackColor?: string;
}

/**
 * Circular progress indicator for ITD portal import jobs.
 *
 * - signing_in: arc grows from 12 o'clock to 6 o'clock (0° → 180°) over 6s.
 * - downloading: arc continues from 6 o'clock back to 12 o'clock (180° → 360°),
 *   holding at ~95% until the job actually completes.
 * - complete: arc snaps to a full ring (360°).
 * - failed: animation stops, ring stays at its last position.
 */
export function PortalProgressCircle({
  phase,
  size = 14,
  color = '#1D6FA4',
  trackColor = 'rgba(0,0,0,0.15)',
}: PortalProgressCircleProps): React.ReactElement {
  const [angle, setAngle] = useState<number>(0);
  const phaseRef = useRef<PortalProgressPhase>(phase);
  phaseRef.current = phase;

  const signStartRef = useRef<number | null>(null);
  const dlStartRef = useRef<number | null>(null);
  const lastPhaseRef = useRef<PortalProgressPhase>(phase);
  const stoppedRef = useRef<boolean>(false);
  const angleRef = useRef<number>(0);

  useEffect(() => {
    let raf = 0;
    stoppedRef.current = false;

    const loop = (t: number): void => {
      if (stoppedRef.current) return;
      const p = phaseRef.current;

      if (p !== lastPhaseRef.current) {
        if (p === 'downloading' && lastPhaseRef.current === 'signing_in') {
          dlStartRef.current = t;
        }
        lastPhaseRef.current = p;
      }

      let next = angleRef.current;
      if (p === 'signing_in') {
        if (signStartRef.current === null) signStartRef.current = t;
        const elapsed = t - signStartRef.current;
        next = Math.min(elapsed / 6000, 1) * 180;
      } else if (p === 'downloading') {
        if (dlStartRef.current === null) dlStartRef.current = t;
        const elapsed = t - dlStartRef.current;
        next = Math.min(180 + (elapsed / 6000) * 160, 340);
      } else if (p === 'complete') {
        next = 360;
      } else if (p === 'failed') {
        stoppedRef.current = true;
        return;
      }

      if (p === 'complete') stoppedRef.current = true;

      if (next !== angleRef.current) {
        angleRef.current = next;
        setAngle(next);
      }
      raf = requestAnimationFrame(loop);
    };

    raf = requestAnimationFrame(loop);
    return () => {
      stoppedRef.current = true;
      cancelAnimationFrame(raf);
    };
  }, []);

  const r = (size - 4) / 2;
  const C = 2 * Math.PI * r;
  const visible = (angle / 360) * C;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ display: 'block' }}>
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={trackColor}
        strokeWidth={2}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeDasharray={`${visible} ${C}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
    </svg>
  );
}
