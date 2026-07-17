import { useState, useEffect } from 'react';
import { useAY } from '../contexts/AYContext';
import { dashboardApi } from '../api/dashboard';
import { clientsApi } from '../api/clients';
import { Spinner } from '../components/ui/Spinner';
import { Badge } from '../components/ui/Badge';

import toast from 'react-hot-toast';

export default function DashboardPage() {
  const { ayParam } = useAY();
  const [stats, setStats] = useState<any>(null);
  const [clients, setClients] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      dashboardApi.getStats(ayParam || undefined),
      clientsApi.list({ assessmentYear: ayParam || undefined })
    ])
      .then(([statsData, clientsData]) => {
        setStats(statsData);
        setClients(clientsData);
      })
      .catch(err => toast.error(err.message))
      .finally(() => setLoading(false));
  }, [ayParam]);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
        <Spinner size={32} />
      </div>
    );
  }

  const progress = stats ? (stats.filed / stats.total) * 100 : 0;

  // Get ITR type breakdown from real client data
  const itrBreakdown = clients.reduce((acc: any, client: any) => {
    const itrType = client.itrType || 'ITR-1';
    acc[itrType] = (acc[itrType] || 0) + 1;
    return acc;
  }, {});

  // Get recent activity from clients (sorted by last updated)
  const recentActivity = clients
    .filter((c: any) => c.updatedAt)
    .sort((a: any, b: any) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
    .slice(0, 5)
    .map((client: any) => {
      const timeDiff = Date.now() - new Date(client.updatedAt).getTime();
      const minutes = Math.floor(timeDiff / 60000);
      const hours = Math.floor(timeDiff / 3600000);
      const days = Math.floor(timeDiff / 86400000);
      
      let timeAgo = '';
      if (days > 0) timeAgo = `${days} day${days > 1 ? 's' : ''} ago`;
      else if (hours > 0) timeAgo = `${hours} hour${hours > 1 ? 's' : ''} ago`;
      else if (minutes > 0) timeAgo = `${minutes} min ago`;
      else timeAgo = 'Just now';

      let action = 'Updated';
      let color = 'var(--info)';
      
      if (client.status === 'FILED') {
        action = `${client.itrType || 'ITR'} filed successfully`;
        color = 'var(--success)';
      } else if (client.status === 'IN_PROGRESS') {
        action = 'Filing in progress';
        color = 'var(--info)';
      } else if (client.status === 'DOC_PENDING') {
        action = 'Documents pending';
        color = 'var(--warning)';
      }

      return {
        client: client.name || 'Unknown Client',
        action,
        time: timeAgo,
        color
      };
    });

  return (
    <div>
      <div style={{
        background: 'var(--gold-pale)',
        padding: '12px 20px',
        borderRadius: 'var(--radius)',
        marginBottom: 24,
        border: '1px solid var(--gold-light)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 8 }}>
          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
            AY 2025-26 Filing Season:
          </span>
          <div className="progress-bar" style={{ flex: 1, maxWidth: 400 }}>
            <div className="progress-fill" style={{ width: `${progress}%`, background: 'var(--gold)' }} />
          </div>
          <span className="mono" style={{ fontWeight: 600 }}>{Math.round(progress)}% complete</span>
        </div>
        <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
          Clients filed: <strong>{stats?.filed || 0}</strong> of <strong>{stats?.total || 0}</strong> | 
          <strong> {stats?.inProgress || 0}</strong> in progress | 
          <strong> {stats?.docPending || 0}</strong> doc pending
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 20, marginBottom: 24 }}>
        {[
          { label: 'Total Clients', value: stats?.total || 0, icon: '👥', color: 'var(--accent-blue)' },
          { label: 'Filed', value: stats?.filed || 0, icon: '✓', color: 'var(--success)' },
          { label: 'In Progress', value: stats?.inProgress || 0, icon: '⏱', color: 'var(--info)' },
          { label: 'Doc Pending', value: stats?.docPending || 0, icon: '📄', color: 'var(--warning)' }
        ].map((stat, idx) => (
          <div key={idx} style={{
            background: 'white',
            padding: 20,
            borderRadius: 'var(--radius)',
            borderLeft: `4px solid ${stat.color}`,
            boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
          }}>
            <div style={{ fontSize: 24, marginBottom: 8 }}>{stat.icon}</div>
            <div className="mono" style={{ fontSize: 28, fontWeight: 600, marginBottom: 4 }}>
              {stat.value}
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{stat.label}</div>
          </div>
        ))}
      </div>

      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        padding: '20px 0',
        marginBottom: 24
      }}>
        {[
          { label: 'Total', value: stats?.total || 0 },
          { label: 'Filed', value: stats?.filed || 0 },
          { label: 'In Progress', value: stats?.inProgress || 0 },
          { label: 'Doc Pending', value: stats?.docPending || 0 },
          { label: 'Mismatch', value: stats?.totalMismatches || 0 }
        ].map((item, idx) => (
          <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {idx > 0 && <span style={{ color: 'var(--text-muted)' }}>→</span>}
            <div style={{
              background: 'white',
              padding: '12px 20px',
              borderRadius: 'var(--radius)',
              border: '1px solid var(--border)'
            }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>
                {item.label}
              </div>
              <div className="mono" style={{ fontSize: 20, fontWeight: 600 }}>
                {item.value}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 20 }}>
        <div style={{
          background: 'white',
          padding: 20,
          borderRadius: 'var(--radius)',
          border: '1px solid var(--border)'
        }}>
          <h3 className="crimson" style={{ fontSize: 18, marginBottom: 16 }}>Recent Activity</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {recentActivity.length > 0 ? recentActivity.map((item, idx) => (
              <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: item.color
                }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{item.client}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{item.action}</div>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{item.time}</div>
              </div>
            )) : (
              <div style={{ fontSize: 13, color: 'var(--text-muted)', textAlign: 'center', padding: 20 }}>
                No recent activity
              </div>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div style={{
            background: 'white',
            padding: 20,
            borderRadius: 'var(--radius)',
            border: '1px solid var(--border)'
          }}>
            <h3 className="crimson" style={{ fontSize: 16, marginBottom: 16 }}>ITR Type Breakdown</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {Object.keys(itrBreakdown).length > 0 ? Object.entries(itrBreakdown).map(([type, count]: [string, any]) => (
                <div key={type}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 12 }}>
                    <span>{type}</span>
                    <span className="mono">{count}</span>
                  </div>
                  <div className="progress-bar">
                    <div className="progress-fill" style={{
                      width: `${(count / clients.length) * 100}%`,
                      background: type === 'ITR-1' ? 'var(--accent-blue)' : 
                                 type === 'ITR-2' ? 'var(--accent-teal)' : 
                                 type === 'ITR-3' ? 'var(--gold)' : 'var(--accent-rose)'
                    }} />
                  </div>
                </div>
              )) : (
                <div style={{ fontSize: 13, color: 'var(--text-muted)', textAlign: 'center', padding: 20 }}>
                  No ITR data available
                </div>
              )}
            </div>
          </div>

          <div style={{
            background: 'white',
            padding: 20,
            borderRadius: 'var(--radius)',
            border: '1px solid var(--border)'
          }}>
            <h3 className="crimson" style={{ fontSize: 16, marginBottom: 16 }}>Today's Deadlines</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[
                { title: 'ITR Filing Deadline', date: '31 Jul 2025', status: 'danger' },
                { title: 'Advance Tax Q1', date: '15 Jun 2025', status: 'info' },
                { title: 'Form 16 Issuance', date: '15 Jun 2025', status: 'warning' }
              ].map((item, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Badge variant={item.status as any}>{item.date}</Badge>
                  <span style={{ fontSize: 12 }}>{item.title}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
