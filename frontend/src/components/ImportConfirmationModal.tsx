/**
 * ImportConfirmationModal — shown after ITD portal automation completes.
 *
 * Presents a summary of reconciled data (or an empty-state warning) before
 * the user confirms import. Uses the same CSS-variable design system as the
 * rest of the app — no Tailwind.
 */
import React from 'react';
import type { ReconciledResults, ReconciledIncomeHead } from '../api/itrAutomation';

// ── Props ────────────────────────────────────────────────────────────────────

export interface ImportConfirmationModalProps {
  show: boolean;
  results: ReconciledResults | null;
  /** Display overrides — provided by the parent page when available. */
  clientName?: string;
  pan?: string;
  assessmentYear?: string;
  onConfirm: () => void;
  onCancel: () => void;
  onRetry?: () => void;
}

// ── Currency formatter ───────────────────────────────────────────────────────

function fmt(val: number): string {
  return '₹' + val.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ── Determine whether we have any usable data ────────────────────────────────

function hasUsableData(results: ReconciledResults | null): boolean {
  if (!results) return false;
  const heads = Object.values(results.income_heads);
  const totalEntries = heads.reduce((sum, h) => sum + h.entries.length, 0);
  const totalIncome = heads.reduce((sum, h) => sum + h.total_final, 0);
  return totalEntries > 0 || totalIncome > 0;
}

// ── Component ────────────────────────────────────────────────────────────────

export default function ImportConfirmationModal({
  show,
  results,
  clientName,
  pan,
  assessmentYear,
  onConfirm,
  onCancel,
  onRetry,
}: ImportConfirmationModalProps) {
  if (!show) return null;

  // ── Derived display values ──────────────────────────────────────────────

  const name = clientName || results?.metadata?.name || '';
  const panDisplay = pan || results?.metadata?.pan || '';
  const fy = assessmentYear || results?.metadata?.financial_year || '';
  const subtitleParts = [name, panDisplay, fy ? `AY ${fy}` : ''].filter(Boolean).join(' • ');

  const hasData = hasUsableData(results);
  const heads = results
    ? Object.values(results.income_heads).filter(h => h.total_final !== 0 || h.entries.length > 0)
    : [];
  const hasDiscrepancies = results ? results.summary.total_discrepancies > 0 : false;
  const hasErrors = results && results._extraction_errors && results._extraction_errors.length > 0;

  // Build a clean status message
  let statusLine: string;
  if (hasData) {
    const s = results!.summary;
    statusLine = `${s.total_entries} income entr${s.total_entries === 1 ? 'y' : 'ies'} imported`;
    if (s.total_final_income > 0) {
      statusLine += ` — total: ${fmt(s.total_final_income)}`;
    }
    if (s.total_discrepancies > 0) {
      statusLine += ` — ${s.total_discrepancies} discrepanc${s.total_discrepancies === 1 ? 'y' : 'ies'} flagged`;
    }
  } else {
    statusLine = 'No reportable income was found in the portal documents.';
  }

  // ── Shared style tokens (consistent with index.css design system) ────────

  const overlay: React.CSSProperties = {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.45)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 2000,
  };

  const card: React.CSSProperties = {
    background: 'var(--bg-card)',
    borderRadius: 'var(--radius)',
    boxShadow: '0 8px 40px rgba(0,0,0,0.18)',
    maxWidth: 620,
    width: 'calc(100% - 32px)',
    maxHeight: '85vh',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  };

  const header: React.CSSProperties = {
    padding: '20px 24px 12px',
    borderBottom: hasData ? '1px solid var(--border)' : 'none',
  };

  const body: React.CSSProperties = {
    padding: '16px 24px 20px',
    overflowY: 'auto',
    flex: 1,
  };

  const footer: React.CSSProperties = {
    padding: '12px 24px',
    borderTop: '1px solid var(--border)',
    background: 'var(--bg)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  };

  // ── Button styles — matching the Save/JSON/PDF pattern on the page ──────

  const btnPrimary: React.CSSProperties = {
    padding: '8px 16px',
    background: 'var(--gold)',
    color: 'white',
    border: 'none',
    borderRadius: 6,
    fontSize: 12,
    fontWeight: 500,
    cursor: 'pointer',
  };

  const btnSecondary: React.CSSProperties = {
    padding: '8px 16px',
    background: 'white',
    color: 'var(--text-secondary)',
    border: '1px solid var(--border-strong)',
    borderRadius: 6,
    fontSize: 12,
    fontWeight: 500,
    cursor: 'pointer',
  };

  const btnDanger: React.CSSProperties = {
    padding: '8px 16px',
    background: 'var(--danger)',
    color: 'white',
    border: 'none',
    borderRadius: 6,
    fontSize: 12,
    fontWeight: 500,
    cursor: 'pointer',
  };

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div style={overlay} onClick={onCancel}>
      <div style={card} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div style={header}>
          <h2 style={{
            fontFamily: "'Crimson Pro', serif",
            fontSize: 20,
            fontWeight: 600,
            color: 'var(--text-primary)',
            margin: 0,
            marginBottom: subtitleParts ? 4 : 0,
          }}>
            Import from Portal
          </h2>
          {subtitleParts && (
            <p style={{
              fontSize: 12,
              color: 'var(--text-muted)',
              margin: 0,
            }}>
              {subtitleParts}
            </p>
          )}
          <p style={{
            fontSize: 13,
            color: hasData ? 'var(--text-secondary)' : 'var(--warning)',
            margin: 0,
            marginTop: 8,
            fontWeight: hasData ? 400 : 500,
          }}>
            {hasData ? statusLine : (
              <>
                <span style={{ marginRight: 4 }}>⚠</span>
                {statusLine}
              </>
            )}
          </p>
        </div>

        {/* Body */}
        {hasData && (
          <div style={body}>
            {/* Income head breakdown as a compact stat row */}
            {heads.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: 'var(--text-muted)',
                  textTransform: 'uppercase',
                  letterSpacing: 0.5,
                  marginBottom: 8,
                }}>
                  Income Summary
                </div>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ background: 'var(--bg)' }}>
                      <th style={thLeft}>Income Head</th>
                      <th style={thRight}>Amount</th>
                      <th style={thRight}>Entries</th>
                      <th style={thRight}>TDS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {heads.map((head: ReconciledIncomeHead) => (
                      <tr key={head.income_head} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={tdLeft}>
                          {head.income_head}
                          {head.discrepancy_count > 0 && (
                            <span style={{
                              marginLeft: 6,
                              fontSize: 10,
                              color: 'var(--warning)',
                              fontWeight: 600,
                            }}>
                              ⚠ {head.discrepancy_count}
                            </span>
                          )}
                        </td>
                        <td style={tdRight} className="mono">{fmt(head.total_final)}</td>
                        <td style={{ ...tdRight, color: 'var(--text-muted)' }}>{head.entries.length}</td>
                        <td style={tdRight} className="mono">
                          {head.total_as26_tds > 0 ? fmt(head.total_as26_tds) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Discrepancies callout */}
            {hasDiscrepancies && (
              <div style={{
                padding: '10px 14px',
                background: 'var(--warning-bg)',
                border: '1px solid var(--warning)',
                borderRadius: 'var(--radius-sm)',
                marginBottom: 12,
                display: 'flex',
                alignItems: 'flex-start',
                gap: 8,
              }}>
                <span style={{ fontSize: 14, flexShrink: 0 }}>⚠️</span>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--warning)' }}>
                    {results!.summary.total_discrepancies} Discrepanc{
                      results!.summary.total_discrepancies === 1 ? 'y' : 'ies'
                    } Found
                  </div>
                  <div style={{ fontSize: 11, color: '#92400e', marginTop: 2 }}>
                    Amounts differ between documents (AIS vs TIS or TIS vs 26AS).
                    The higher value will be used. Review flagged entries after import.
                  </div>
                </div>
              </div>
            )}

            {/* Unmatched entries warning */}
            {(() => {
              const unmatchedTotal =
                (results!.unmatched?.tis_only?.length ?? 0) +
                (results!.unmatched?.ais_only?.length ?? 0) +
                (results!.unmatched?.as26_only?.length ?? 0);
              if (unmatchedTotal === 0) return null;
              return (
                <div style={{
                  padding: '10px 14px',
                  background: 'var(--info-bg)',
                  border: '1px solid var(--info)',
                  borderRadius: 'var(--radius-sm)',
                  marginBottom: 12,
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 8,
                }}>
                  <span style={{ fontSize: 14, flexShrink: 0 }}>ℹ️</span>
                  <div style={{ fontSize: 12, color: 'var(--info)' }}>
                    {unmatchedTotal} entr{unmatchedTotal === 1 ? 'y' : 'ies'} could not be matched
                    across documents and will be skipped.
                  </div>
                </div>
              );
            })()}
          </div>
        )}

        {/* Empty / failed state body */}
        {!hasData && (
          <div style={body}>
            {/* Extraction errors — warning callout */}
            {hasErrors && (
              <div style={{
                padding: '12px 14px',
                background: 'var(--danger-bg)',
                border: '1px solid var(--danger)',
                borderRadius: 'var(--radius-sm)',
                marginBottom: 12,
              }}>
                <div style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: 'var(--danger)',
                  marginBottom: 6,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}>
                  <span>⚠</span> Extraction Errors
                </div>
                <ul style={{
                  margin: 0,
                  paddingLeft: 18,
                  fontSize: 12,
                  color: '#991b1b',
                  lineHeight: 1.6,
                }}>
                  {results!._extraction_errors!.map((err: string, idx: number) => (
                    <li key={idx}>{err}</li>
                  ))}
                </ul>
              </div>
            )}
            {!hasErrors && (
              <div style={{
                padding: '24px 0',
                textAlign: 'center',
                color: 'var(--text-muted)',
              }}>
                <div style={{ fontSize: 32, marginBottom: 8 }}>📭</div>
                <div style={{ fontSize: 13 }}>The portal documents exist but contain no reportable income data.</div>
              </div>
            )}
          </div>
        )}

        {/* Data source line — as footer prefix */}
        <div style={footer}>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            Data source: ITD portal{fy ? ` • ${fy}` : ''}{panDisplay ? ` • ${panDisplay}` : ''}
          </span>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={onCancel}
              style={btnSecondary}
            >
              Cancel
            </button>
            {hasData ? (
              <button
                onClick={onConfirm}
                style={btnPrimary}
              >
                Confirm &amp; Import
              </button>
            ) : (
              <button
                onClick={onRetry || onCancel}
                style={btnDanger}
              >
                Retry
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Shared table cell styles ─────────────────────────────────────────────────

const thLeft: React.CSSProperties = {
  padding: '7px 10px',
  fontSize: 10.5,
  fontWeight: 600,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: 0.3,
  textAlign: 'left',
};

const thRight: React.CSSProperties = {
  ...thLeft,
  textAlign: 'right',
};

const tdLeft: React.CSSProperties = {
  padding: '8px 10px',
  fontSize: 12.5,
  color: 'var(--text-primary)',
  verticalAlign: 'middle',
};

const tdRight: React.CSSProperties = {
  ...tdLeft,
  textAlign: 'right',
  fontFamily: "'DM Mono', monospace",
  fontSize: 12,
};
