import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAY } from '../contexts/AYContext';
import { filingApi } from '../api/filing';
import { SkeletonRow } from '../components/ui/SkeletonRow';
import { EmptyState } from '../components/ui/EmptyState';
import { Badge } from '../components/ui/Badge';
import { INR } from '../utils/formatters';
import toast from 'react-hot-toast';

export default function FilingPage() {
  const { ayParam } = useAY();
  const navigate = useNavigate();
  const [filings, setFilings] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    filingApi.list({ assessmentYear: ayParam || undefined })
      .then(setFilings)
      .catch(err => toast.error(err.message))
      .finally(() => setLoading(false));
  }, [ayParam]);

  const getStatusBadge = (status: string) => {
    const map: Record<string, any> = {
      'Filed': 'success',
      'Ready to File': 'gold',
      'In Progress': 'info',
      'Doc Pending': 'warning',
      'Mismatch': 'danger'
    };
    return map[status] || 'muted';
  };

  const stageCounts = {
    mismatch: filings.filter(f => f.status === 'Mismatch').length,
    reconciliation: filings.filter(f => f.status === 'In Progress').length,
    ready: filings.filter(f => f.status === 'Ready to File').length,
    docPending: filings.filter(f => f.status === 'Doc Pending').length,
    filed: filings.filter(f => f.status === 'Filed').length
  };

  return (
    <div>
      <h1 className="crimson" style={{ fontSize: 22, marginBottom: 24 }}>ITR Filing</h1>

      <div style={{
        display: 'flex',
        gap: 16,
        marginBottom: 24,
        overflowX: 'auto'
      }}>
        {[
          { label: 'Mismatch Review', count: stageCounts.mismatch, color: 'var(--danger)' },
          { label: 'Reconciliation', count: stageCounts.reconciliation, color: 'var(--info)' },
          { label: 'Ready to File', count: stageCounts.ready, color: 'var(--gold)' },
          { label: 'Doc Pending', count: stageCounts.docPending, color: 'var(--warning)' },
          { label: 'Filed', count: stageCounts.filed, color: 'var(--success)' }
        ].map((stage, idx) => (
          <div key={idx} style={{
            flex: 1,
            minWidth: 150,
            background: 'white',
            padding: 16,
            borderRadius: 'var(--radius)',
            border: '1px solid var(--border)',
            borderTop: `3px solid ${stage.color}`
          }}>
            <div className="mono" style={{ fontSize: 24, fontWeight: 600, marginBottom: 4 }}>
              {stage.count}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
              {stage.label}
            </div>
          </div>
        ))}
      </div>

      <div style={{ background: 'white', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
        <table>
          <thead>
            <tr>
              <th>Client</th>
              <th>ITR Form</th>
              <th>Filing Stage</th>
              <th>Tax Payable / Refund</th>
              <th>Last Updated</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && <SkeletonRow cols={6} />}
            {!loading && filings.length === 0 && (
              <tr>
                <td colSpan={6}>
                  <EmptyState message="No filings found" />
                </td>
              </tr>
            )}
            {!loading && filings.map((filing) => (
              <tr key={filing.id}>
                <td>
                  <div>
                    <div style={{ fontWeight: 500 }}>{filing.clientName}</div>
                    <div className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      {filing.clientPan}
                    </div>
                  </div>
                </td>
                <td>
                  <Badge variant="navy">{filing.itrType}</Badge>
                </td>
                <td>
                  <Badge variant={getStatusBadge(filing.status)}>
                    {filing.status}
                  </Badge>
                </td>
                <td className="mono">
                  {filing.refundAmount ? (
                    <span style={{ color: 'var(--success)' }}>
                      {INR(filing.refundAmount)} Refund
                    </span>
                  ) : filing.taxPayable ? (
                    <span style={{ color: 'var(--warning)' }}>
                      {INR(filing.taxPayable)} Payable
                    </span>
                  ) : '-'}
                </td>
                <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                  {filing.updatedAt ? new Date(filing.updatedAt).toLocaleDateString() : '-'}
                </td>
                <td>
                  <button
                    onClick={() => navigate(`/filing/${filing.clientId}/${filing.assessmentYear}`)}
                    style={{
                      padding: '6px 12px',
                      background: 'var(--accent-blue)',
                      color: 'white',
                      border: 'none',
                      borderRadius: 4,
                      fontSize: 12,
                      fontWeight: 500,
                      cursor: 'pointer'
                    }}
                  >
                    Open ITR
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
