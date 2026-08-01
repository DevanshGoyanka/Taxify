import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAY } from '../contexts/AYContext';
import { clientsApi } from '../api/clients';
import { panApi } from '../api/pan';
import { SkeletonRow } from '../components/ui/SkeletonRow';
import { EmptyState } from '../components/ui/EmptyState';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import { panInitials, deriveEntityFromPAN } from '../utils/formatters';
import type { ClientRecord } from '../types/client.types';
import toast from 'react-hot-toast';

export default function ClientsPage() {
  const { ayParam } = useAY();
  const navigate = useNavigate();
  const [clients, setClients] = useState<ClientRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingClient, setEditingClient] = useState<any>(null);

  const loadClients = () => {
    setLoading(true);
    clientsApi.list({ assessmentYear: ayParam || undefined, search: searchQuery || undefined })
      .then(setClients)
      .catch(err => toast.error(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadClients();
  }, [ayParam, searchQuery]);

  const getStatusBadge = (status: string) => {
    const map: Record<string, any> = {
      'Filed': 'success',
      'In Progress': 'info',
      'Doc Pending': 'warning',
      'Mismatch': 'danger',
      'Ready to File': 'gold',
      'Not Started': 'muted'
    };
    return map[status] || 'muted';
  };

  const handleArchive = async (id: string, name: string) => {
    if (!confirm(`Archive ${name}? Their prior-year returns will be preserved and the client can be restored later.`)) return;
    try {
      await clientsApi.archive(id);
      toast.success('Client archived');
      loadClients();
    } catch (err: any) {
      toast.error(err.message);
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1 className="crimson" style={{ fontSize: 22 }}>Client Master</h1>
        <div style={{ display: 'flex', gap: 12 }}>
          <input
            type="text"
            placeholder="Search clients, PAN..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              padding: '8px 12px',
              border: '1px solid var(--border)',
              borderRadius: 6,
              fontSize: 13,
              width: 250
            }}
          />
          <button
            onClick={() => setShowAddModal(true)}
            style={{
              padding: '8px 16px',
              background: 'var(--gold)',
              color: 'white',
              border: 'none',
              borderRadius: 6,
              fontSize: 13,
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            Add Client
          </button>
        </div>
      </div>

      <div style={{ background: 'white', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
        <table>
          <thead>
            <tr>
              <th>Client</th>
              <th>PAN</th>
              <th>Type</th>
              <th>ITR Form</th>
              <th>AY Status</th>
              <th>Last Sync</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && <SkeletonRow cols={7} />}
            {!loading && clients.length === 0 && (
              <tr>
                <td colSpan={7}>
                  <EmptyState message="No clients found" />
                </td>
              </tr>
            )}
            {!loading && clients.map((client) => {
              const latestYear = client.years?.[0];
              return (
                <tr key={client.id}>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{
                        width: 32,
                        height: 32,
                        borderRadius: '50%',
                        background: 'var(--gold)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'var(--navy)',
                        fontWeight: 600,
                        fontSize: 12
                      }}>
                        {panInitials(client.name)}
                      </div>
                      <div>
                        <div style={{ fontWeight: 500 }}>{client.name}</div>
                        <div className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                          {client.pan}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="mono">{client.pan}</td>
                  <td>
                    <Badge variant="muted">{deriveEntityFromPAN(client.pan)}</Badge>
                  </td>
                  <td>
                    <Badge variant="navy">{latestYear?.itrType || 'N/A'}</Badge>
                  </td>
                  <td>
                    <Badge variant={getStatusBadge(latestYear?.status)}>
                      {latestYear?.status || 'Not Started'}
                    </Badge>
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                    {client.updatedAt ? new Date(client.updatedAt).toLocaleDateString() : '-'}
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button
                        onClick={() => navigate(`/filing/${client.publicId}/${latestYear?.year || ayParam || '2026-27'}`)}
                        style={{
                          padding: '4px 8px',
                          background: 'var(--accent-blue)',
                          color: 'white',
                          border: 'none',
                          borderRadius: 4,
                          fontSize: 11,
                          cursor: 'pointer'
                        }}
                      >
                        Open ITR
                      </button>
                      <button
                        onClick={() => setEditingClient(client)}
                        style={{
                          padding: '4px 8px',
                          background: 'var(--border)',
                          border: 'none',
                          borderRadius: 4,
                          fontSize: 11,
                          cursor: 'pointer'
                        }}
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleArchive(client.publicId, client.name)}
                        style={{
                          padding: '4px 8px',
                          background: 'var(--danger-bg)',
                          color: 'var(--danger)',
                          border: 'none',
                          borderRadius: 4,
                          fontSize: 11,
                          cursor: 'pointer'
                        }}
                      >
                        Archive
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {(showAddModal || editingClient) && (
        <ClientModal
          client={editingClient}
          onClose={() => {
            setShowAddModal(false);
            setEditingClient(null);
          }}
          onSave={() => {
            setShowAddModal(false);
            setEditingClient(null);
            loadClients();
          }}
        />
      )}
    </div>
  );
}

function ClientModal({ client, onClose, onSave }: any) {
  const [formData, setFormData] = useState({
    pan: client?.pan || '',
    name: client?.name || '',
    email: client?.email || '',
    mobile: client?.mobile || '',
    aadhaar: client?.aadhaar || '',
    dob: client?.dob || '',
    portal_password: ''
  });
  const [panStatus, setPanStatus] = useState<'valid' | 'invalid' | null>(null);
  const [entityType, setEntityType] = useState('');
  const [recommendedITR, setRecommendedITR] = useState('');
  const [itrReason, setItrReason] = useState('');
  const [loading, setLoading] = useState(false);

  const handlePanBlur = async () => {
    if (formData.pan.length !== 10) return;
    try {
      const result = await panApi.analyze(formData.pan);
      setPanStatus(result.valid ? 'valid' : 'invalid');
      setEntityType(result.entityType);
      if (result.warnings.length) {
        toast(result.warnings.join(', '), { icon: '⚠️' });
      }
      
      // Auto-classify ITR form
      if (result.valid) {
        try {
          const incomeProfile = {
            pan: formData.pan,
            totalIncome: 0,
            hasCapitalGains: false,
            hasBusinessIncome: false,
            hasMultipleProperties: false,
            hasForeignIncome: false,
            hasProfessionalIncome: false,
            residentialStatus: 'RES',
            isDirector: false,
            hasUnlistedShares: false,
            agriculturalIncome: 0,
            hasLotteryIncome: false,
            hasRaceHorseIncome: false,
            eligibleFor44AD: false,
            eligibleFor44ADA: false,
            eligibleFor44AE: false
          };
          
          // Use a temporary client ID of 0 for new clients
          const classification = await clientsApi.classifyITR(client?.id || 0, incomeProfile);
          setRecommendedITR(classification.recommendedForm);
          setItrReason(classification.classificationReason);
          toast.success(`Recommended ITR: ${classification.recommendedForm}`);
        } catch (err) {
          console.error('ITR classification failed:', err);
        }
      }
    } catch {
      setPanStatus('invalid');
    }
  };

  const handleSubmit = async (e: any) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (client) {
        const payload: any = { ...formData };
        if (!payload.portal_password) {
          delete payload.portal_password;
        }
        await clientsApi.update(client.publicId || client.id, payload);
        toast.success('Client updated');
      } else {
        await clientsApi.create(formData);
        toast.success('Client added');
      }
      onSave();
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0,0,0,0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000
    }}>
      <div style={{
        background: 'white',
        borderRadius: 'var(--radius)',
        padding: 32,
        width: 500,
        maxWidth: '90%',
        maxHeight: '90vh',
        overflowY: 'auto'
      }}>
        <h2 className="crimson" style={{ fontSize: 20, marginBottom: 24 }}>
          {client ? 'Edit Client' : 'Add Client'}
        </h2>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
              PAN *
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                value={formData.pan}
                onChange={(e) => setFormData({ ...formData, pan: e.target.value.toUpperCase() })}
                onBlur={handlePanBlur}
                maxLength={10}
                required
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  fontSize: 13
                }}
              />
              {panStatus && (
                <span style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)' }}>
                  {panStatus === 'valid' ? '✓' : '✗'}
                </span>
              )}
            </div>
            {entityType && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
              Entity: {entityType}
            </div>}
            {recommendedITR && (
              <div style={{ 
                fontSize: 11, 
                color: 'var(--accent-blue)', 
                marginTop: 4,
                padding: '4px 8px',
                background: 'var(--accent-blue-bg)',
                borderRadius: 4,
                fontWeight: 500
              }}>
                Recommended ITR: {recommendedITR}
                {itrReason && <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                  {itrReason}
                </div>}
              </div>
            )}
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
              Name * (CBDT Mandatory)
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
              style={{
                width: '100%',
                padding: '8px 12px',
                border: '1px solid var(--border)',
                borderRadius: 6,
                fontSize: 13
              }}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
                Email
              </label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  fontSize: 13
                }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
                Mobile
              </label>
              <input
                type="tel"
                value={formData.mobile}
                onChange={(e) => setFormData({ ...formData, mobile: e.target.value })}
                maxLength={10}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  fontSize: 13
                }}
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
                Aadhaar
              </label>
              <input
                type="text"
                value={formData.aadhaar}
                onChange={(e) => setFormData({ ...formData, aadhaar: e.target.value })}
                maxLength={12}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  fontSize: 13
                }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
                Date of Birth * (CBDT Mandatory)
              </label>
              <input
                type="date"
                value={formData.dob}
                onChange={(e) => setFormData({ ...formData, dob: e.target.value })}
                required
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  fontSize: 13
                }}
              />
            </div>
          </div>

          <div style={{ marginBottom: 24 }}>
            <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
              Portal Password
            </label>
            <input
              type="password"
              value={formData.portal_password}
              onChange={(e) => setFormData({ ...formData, portal_password: e.target.value })}
              autoComplete="new-password"
              style={{
                width: '100%',
                padding: '8px 12px',
                border: '1px solid var(--border)',
                borderRadius: 6,
                fontSize: 13
              }}
            />
          </div>

          <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: '8px 16px',
                background: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                fontSize: 13,
                cursor: 'pointer'
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              style={{
                padding: '8px 16px',
                background: loading ? 'var(--border)' : 'var(--gold)',
                color: 'white',
                border: 'none',
                borderRadius: 6,
                fontSize: 13,
                fontWeight: 600,
                cursor: loading ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 8
              }}
            >
              {loading && <Spinner size={14} />}
              {loading ? 'Saving...' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
