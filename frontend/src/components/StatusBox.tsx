/**
 * StatusBox — live progress indicator for ITD portal automation jobs.
 *
 * Mounted next to the "Import" button on ITRComputationPage.
 * Polls GET /automation/jobs/{job_id} every 2 s while the job is active
 * and renders a clean, user-friendly step-by-step progress bar.
 */
import React, { useEffect, useRef, useState } from 'react';
import { itrAutomationApi } from '../api/itrAutomation';
import type { AutomationJob } from '../api/itrAutomation';
import { Spinner } from './ui/Spinner';

// ── Props ────────────────────────────────────────────────────────────────────

export interface StatusBoxProps {
  jobId: number;
  onComplete: (job: AutomationJob) => void;
  onFailed: (job: AutomationJob) => void;
  onDismiss: () => void;
}

// ── Mapping: current_step → user-friendly step label + icon ──────────────────

const STEP_INFO: Record<string, { label: string; icon: string }> = {
  login:          { label: 'Signing into ITD portal',        icon: '🔐' },
  download_26as:  { label: 'Downloading Form 26AS',          icon: '📄' },
  request_ais:    { label: 'Requesting AIS generation',       icon: '📋' },
  download_tis:   { label: 'Downloading TIS statement',      icon: '📥' },
  poll_ais:       { label: 'Waiting for AIS generation',      icon: '⏳' },
  unlock:         { label: 'Decrypting downloaded PDFs',      icon: '🔓' },
  extract:        { label: 'Extracting & reconciling data',   icon: '📊' },
  logout:         { label: 'Signing out of portal',           icon: '🚪' },
};

// Ordered list of all possible steps for the timeline display
const ALL_STEPS = [
  'login',
  'download_26as',
  'request_ais',
  'download_tis',
  'poll_ais',
  'unlock',
  'extract',
  'logout',
];

// ── Component ────────────────────────────────────────────────────────────────

export default function StatusBox({ jobId, onComplete, onFailed, onDismiss }: StatusBoxProps) {
  const [job, setJob] = useState<AutomationJob | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Poll the job status every 2 seconds
  useEffect(() => {
    const poll = async () => {
      try {
        const data = await itrAutomationApi.getJobStatus(jobId);
        setJob(data);

        if (data.status === 'completed') {
          if (pollRef.current) clearInterval(pollRef.current);
          onComplete(data);
        } else if (data.status === 'failed') {
          if (pollRef.current) clearInterval(pollRef.current);
          onFailed(data);
        }
      } catch {
        // Silently ignore poll errors — retry next tick
      }
    };

    poll(); // immediate first fetch
    pollRef.current = setInterval(poll, 2000);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [jobId, onComplete, onFailed]);

  if (!job) {
    return (
      <Box>
        <Row>
          <Spinner size={14} />
          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            Connecting to automation service…
          </span>
        </Row>
      </Box>
    );
  }

  const isDone = job.status === 'completed';
  const isFail = job.status === 'failed';

  return (
    <Box>
      {/* Header */}
      <Row style={{ justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>
          Import from Portal
        </span>
        <button
          onClick={onDismiss}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontSize: 14,
            color: 'var(--text-secondary)',
            padding: 0,
            lineHeight: 1,
          }}
        >
          ✕
        </button>
      </Row>

      {/* Progress bar */}
      <div
        style={{
          height: 4,
          borderRadius: 2,
          background: 'var(--border)',
          marginBottom: 10,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${Math.max(job.progress_pct ?? 0, isDone ? 100 : isFail ? 0 : 2)}%`,
            background: isFail ? 'var(--danger)' : 'var(--gold)',
            transition: 'width 0.6s ease',
            borderRadius: 2,
          }}
        />
      </div>

      {/* Current step / completion message */}
      <Row style={{ marginBottom: 8 }}>
        {!isDone && !isFail && <Spinner size={12} />}
        {isDone && <span style={{ fontSize: 14 }}>✅</span>}
        {isFail && <span style={{ fontSize: 14 }}>❌</span>}
        <span
          style={{
            fontSize: 12,
            color: isFail ? 'var(--danger)' : 'var(--text-secondary)',
            fontWeight: isDone ? 500 : 400,
          }}
        >
          {isDone
            ? 'All downloads complete'
            : isFail
              ? job.status_message || 'Automation failed'
              : job.progress_label || job.status_message || 'Preparing…'}
        </span>
      </Row>

      {/* Step timeline */}
      <Timeline currentStep={job.current_step} stepsCompleted={job.steps_completed} />

      {/* Error details */}
      {isFail && job.error_message && (
        <div
          style={{
            fontSize: 11,
            color: 'var(--danger)',
            marginTop: 8,
            padding: '6px 8px',
            background: 'rgba(220,38,38,0.08)',
            borderRadius: 4,
            whiteSpace: 'pre-wrap',
            maxHeight: 80,
            overflowY: 'auto',
          }}
        >
          {job.error_message.slice(0, 300)}
        </div>
      )}

      {/* Elapsed time */}
      {job.started_at && (
        <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 6 }}>
          Started {formatElapsed(job.started_at)}
          {job.completed_at && ` • Took ${formatDuration(job.started_at, job.completed_at)}`}
        </div>
      )}
    </Box>
  );
}

// ── Sub-components ───────────────────────────────────────────────────────────

function Box({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        background: 'white',
        border: '1px solid var(--border)',
        borderRadius: 8,
        padding: 12,
        marginTop: 6,
        minWidth: 260,
        maxWidth: 320,
        boxShadow: '0 4px 16px rgba(0,0,0,0.1)',
      }}
    >
      {children}
    </div>
  );
}

function Row({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, ...style }}>
      {children}
    </div>
  );
}

function Timeline({
  currentStep,
  stepsCompleted,
}: {
  currentStep: string | null;
  stepsCompleted: string[];
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {ALL_STEPS.map((key) => {
        const info = STEP_INFO[key];
        if (!info) return null;

        const isCompleted = stepsCompleted.includes(`${key}_downloaded`) || stepsCompleted.includes(key);
        const isCurrent = currentStep === key;
        const isPending = !isCompleted && !isCurrent;

        return (
          <div
            key={key}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 11,
              color: isPending ? 'var(--border)' : 'var(--text-secondary)',
              fontWeight: isCurrent ? 500 : 400,
              opacity: isPending ? 0.5 : 1,
              transition: 'all 0.3s ease',
            }}
          >
            {/* Status dot */}
            <span style={{ width: 16, textAlign: 'center', fontSize: 10 }}>
              {isCompleted ? '✅' : isCurrent ? '●' : '○'}
            </span>
            {/* Label */}
            <span>{info.icon} {info.label}</span>
          </div>
        );
      })}
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatElapsed(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  if (ms < 60_000) return 'just now';
  const mins = Math.floor(ms / 60_000);
  if (mins === 1) return '1 minute ago';
  if (mins < 60) return `${mins} minutes ago`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m ago`;
}

function formatDuration(start: string, end: string): string {
  const ms = new Date(end).getTime() - new Date(start).getTime();
  const secs = Math.floor(ms / 1000);
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ${secs % 60}s`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m`;
}
