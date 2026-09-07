import { useState, useEffect, useRef, type JSX } from 'react';
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
import './ClientsPage.css';

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
      <div className="clients-page-heading">
        <div className="clients-page-title-group">
          <div className="clients-search" role="search">
            <span className="clients-search-icon" aria-hidden="true">⌕</span>
            <input
              type="text"
              placeholder="Search client"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Search client"
            />
          </div>
        </div>
        <button
          className="clients-add-button"
          onClick={() => setShowAddModal(true)}
        >
          Add Client
        </button>
      </div>
      <div className="clients-table">
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
                <tr key={client.publicId || client.id}>
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
                          background: '#15803D',
                          color: 'white',
                          border: 'none',
                          borderRadius: 4,
                          fontSize: 11,
                          fontWeight: 700,
                          cursor: 'pointer'
                        }}
                      >
                        Open ITR
                      </button>
                      <button
                        onClick={() => setEditingClient(client)}
                        style={{
                          padding: '4px 8px',
                          background: '#374151',
                          color: 'white',
                          border: 'none',
                          borderRadius: 4,
                          fontSize: 11,
                          fontWeight: 700,
                          cursor: 'pointer'
                        }}
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleArchive(client.publicId, client.name)}
                        style={{
                          padding: '4px 8px',
                          background: '#F59E0B',
                          color: '#000000',
                          border: 'none',
                          borderRadius: 4,
                          fontSize: 11,
                          fontWeight: 700,
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

function ClientDatePicker({ value, onChange }: { value: string; onChange: (value: string) => void }): JSX.Element {
  const initialDate = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T00:00:00`) : new Date();
  const [open, setOpen] = useState(false);
  const [visibleMonth, setVisibleMonth] = useState(new Date(initialDate.getFullYear(), initialDate.getMonth(), 1));
  const ref = useRef<HTMLDivElement>(null);
  const selectedDate = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T00:00:00`) : null;
  const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const years = Array.from({ length: 101 }, (_, index) => 1920 + index);
  const firstDay = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth(), 1).getDay();
  const daysInMonth = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() + 1, 0).getDate();
  const cells = Array.from({ length: Math.ceil((firstDay + daysInMonth) / 7) * 7 }, (_, index) => {
    const day = index - firstDay + 1;
    return day >= 1 && day <= daysInMonth ? day : null;
  });

  useEffect(() => {
    const close = (event: MouseEvent): void => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const chooseDay = (day: number): void => {
    onChange(`${visibleMonth.getFullYear()}-${String(visibleMonth.getMonth() + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`);
    setOpen(false);
  };

  return <div ref={ref} className="verification-date-picker client-date-picker">
    <button type="button" className="verification-date-trigger" onClick={() => setOpen((current) => !current)} aria-expanded={open}>
      <span>{selectedDate ? selectedDate.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : 'Pick a date'}</span><span aria-hidden="true">▣</span>
    </button>
    {open && <div className="verification-calendar" role="dialog" aria-label="Choose date of birth">
      <div className="verification-calendar-header">
        <button type="button" onClick={() => setVisibleMonth((current) => new Date(current.getFullYear(), current.getMonth() - 1, 1))} aria-label="Previous month">‹</button>
        <select value={visibleMonth.getMonth()} onChange={(event) => setVisibleMonth(new Date(visibleMonth.getFullYear(), Number(event.target.value), 1))} aria-label="Month">{months.map((month, index) => <option key={month} value={index}>{month}</option>)}</select>
        <select value={visibleMonth.getFullYear()} onChange={(event) => setVisibleMonth(new Date(Number(event.target.value), visibleMonth.getMonth(), 1))} aria-label="Year">{years.map((year) => <option key={year} value={year}>{year}</option>)}</select>
        <button type="button" onClick={() => setVisibleMonth((current) => new Date(current.getFullYear(), current.getMonth() + 1, 1))} aria-label="Next month">›</button>
      </div>
      <div className="verification-calendar-weekdays">{['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((day) => <span key={day}>{day}</span>)}</div>
      <div className="verification-calendar-grid">{cells.map((day, index) => day === null ? <span key={`empty-${index}`} /> : <button key={day} type="button" className={selectedDate && selectedDate.getFullYear() === visibleMonth.getFullYear() && selectedDate.getMonth() === visibleMonth.getMonth() && selectedDate.getDate() === day ? 'selected' : ''} onClick={() => chooseDay(day)}>{day}</button>)}</div>
    </div>}
  </div>;
}

function ClientModal({ client, onClose, onSave }: any) {
  const [formData, setFormData] = useState({
    pan: client?.pan || '',
    firstName: client?.firstName || client?.first_name || '',
    middleName: client?.middleName || client?.middle_name || '',
    surname: client?.surname || '',
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
        await clientsApi.update(client.publicId, payload);
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
      <div className="client-modal" style={{
        background: 'white',
        borderRadius: 'var(--radius)',
        padding: 32,
        width: 500,
        maxWidth: '90%',
        maxHeight: '90vh',
        overflowY: 'auto'
      }}>
        <h2 className="client-modal-title" style={{ fontSize: 20, marginBottom: 24 }}>
          {client ? 'Edit Client' : 'Add Client'}
        </h2>

        <form className="client-modal-form" onSubmit={handleSubmit}>
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
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
              <input
                type="text"
                placeholder="First Name"
                value={formData.firstName}
                onChange={(e) => setFormData({ ...formData, firstName: e.target.value, name: [e.target.value, formData.middleName, formData.surname].filter(Boolean).join(' ') })}
                maxLength={25}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  fontSize: 13
                }}
              />
              <input
                type="text"
                placeholder="Middle Name"
                value={formData.middleName}
                onChange={(e) => setFormData({ ...formData, middleName: e.target.value, name: [formData.firstName, e.target.value, formData.surname].filter(Boolean).join(' ') })}
                maxLength={25}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  fontSize: 13
                }}
              />
              <input
                type="text"
                placeholder="Surname *"
                value={formData.surname}
                onChange={(e) => setFormData({ ...formData, surname: e.target.value, name: [formData.firstName, formData.middleName, e.target.value].filter(Boolean).join(' ') || e.target.value })}
                required
                maxLength={75}
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
              <ClientDatePicker value={formData.dob} onChange={(value) => setFormData({ ...formData, dob: value })} />
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
                background: loading ? 'var(--border)' : '#16a34a',
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
