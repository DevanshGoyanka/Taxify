/**
 * StatusPill — compact inline status indicator for ITD portal automation jobs.
 *
 * Renders as a small pill/badge next to the Import button, matching the
 * existing site design system (navy/gold palette, badge sizing).
 * Coarse states only: signing in → downloading → complete (auto-dismiss).
 * No modal, no progress bar, no step checklist, no emojis.
 */
import React, { useEffect, useRef, useState } from 'react';
import { itrAutomationApi } from '../api/itrAutomation';
import type { AutomationJob } from '../api/itrAutomation';

// ── Props ────────────────────────────────────────────────────────────────────

export interface StatusPillProps {
  jobId: number;
  onComplete: (job: AutomationJob) => void;
  onFailed: (job: AutomationJob) => void;
  onDismiss: () => void;
}

// ── Coarse status mapping ────────────────────────────────────────────────────

type CoarseStatus = 'signing_in' | 'downloading' | 'complete' | 'failed';

function mapStepToCoarseStatus(step: string | null): CoarseStatus {
  if (!step) return 'signing_in';
  if (step === 'login' || step === 'logout') return 'signing_in';
  return 'downloading';
}

const STATUS_LABEL: Record<CoarseStatus, string> = {
  signing_in: 'Signing in…',
  downloading: 'Downloading…',
  complete: 'Import complete',
  failed: 'Import failed',
};

// ── Component ────────────────────────────────────────────────────────────────

export default function StatusPill({ jobId, onComplete, onFailed, onDismiss }: StatusPillProps) {
  const [job, setJob] = useState<AutomationJob | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const autoDismissRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Store latest callbacks in refs to avoid re-running the effect on every
  // render (the root cause of the duplicate/stacking status card bug).
  const onCompleteRef = useRef(onComplete);
  const onFailedRef = useRef(onFailed);
  const onDismissRef = useRef(onDismiss);
  onCompleteRef.current = onComplete;
  onFailedRef.current = onFailed;
  onDismissRef.current = onDismiss;

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const data = await itrAutomationApi.getJobStatus(jobId);
        if (cancelled) return;
        setJob(data);

        if (data.status === 'completed') {
          if (pollRef.current) clearInterval(pollRef.current);
          onCompleteRef.current(data);
          // Auto-dismiss after 4 seconds on success
          autoDismissRef.current = setTimeout(() => onDismissRef.current(), 4000);
        } else if (data.status === 'failed') {
          if (pollRef.current) clearInterval(pollRef.current);
          onFailedRef.current(data);
        }
      } catch {
        // Silently ignore poll errors — retry on next tick
      }
    };

    poll(); // immediate first fetch
    pollRef.current = setInterval(poll, 2000);

    return () => {
      cancelled = true;
      if (pollRef.current) clearInterval(pollRef.current);
      if (autoDismissRef.current) clearTimeout(autoDismissRef.current);
    };
  }, [jobId]); // ONLY depend on jobId — not the callbacks (handled via refs)

  // ── Derive display state ─────────────────────────────────────────────────

  if (!job) {
    return (
      <span className="badge badge-info" style={pillStyle}>
        Connecting…
      </span>
    );
  }

  const isDone = job.status === 'completed';
  const isFail = job.status === 'failed';
  const coarseStatus: CoarseStatus = isDone
    ? 'complete'
    : isFail
      ? 'failed'
      : mapStepToCoarseStatus(job.current_step);

  const variant = isDone ? 'success' : isFail ? 'danger' : 'info';

  return (
    <span
      className={`badge badge-${variant}`}
      style={pillStyle}
      title={isFail && job.error_message ? job.error_message.slice(0, 200) : undefined}
    >
      {!isDone && !isFail && (
        <span
          style={{
            display: 'inline-block',
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: 'currentColor',
            animation: 'pulse 1.2s ease-in-out infinite',
          }}
        />
      )}
      {isDone && (
        <svg width="10" height="10" viewBox="0 0 10 10" style={{ display: 'inline-block' }}>
          <path
            d="M2 5l2 2 4-4"
            stroke="currentColor"
            strokeWidth="1.5"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      )}
      <span>{STATUS_LABEL[coarseStatus]}</span>
      {!isDone && !isFail && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            if (pollRef.current) clearInterval(pollRef.current);
            onDismissRef.current();
          }}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: 0,
            margin: 0,
            marginLeft: 2,
            fontSize: 10,
            color: 'inherit',
            opacity: 0.6,
            lineHeight: 1,
          }}
          title="Cancel import"
        >
          ✕
        </button>
      )}
    </span>
  );
}

// ── Shared pill style — matches Import button height & site radius ───────────

const pillStyle: React.CSSProperties = {
  fontSize: 11.5,
  padding: '5px 10px',
  borderRadius: 'var(--radius-sm)',
  lineHeight: 1.3,
  userSelect: 'none',
};
