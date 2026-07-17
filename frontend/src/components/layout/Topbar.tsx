import { useLocation } from 'react-router-dom';

export const Topbar = () => {
  const location = useLocation();

  const getBreadcrumb = () => {
    const pathMap: Record<string, string> = {
      '/dashboard': 'Dashboard',
      '/clients': 'Client Master',
      '/filing': 'ITR Filing',
      '/reconciliation': 'Reconciliation',
      '/sync': 'ITD Portal Sync',
      '/jobs': 'Background Jobs',
      '/notices': 'Notice Management',
      '/calendar': 'Compliance Calendar',
      '/tasks': 'Tasks & Work Queue',
      '/billing': 'Billing & Fees',
      '/accounting': 'Firm Accounting',
      '/reports': 'Reports & Analytics',
      '/communication': 'Communication'
    };
    return pathMap[location.pathname] || 'Dashboard';
  };

  return (
    <div style={{
      height: 'var(--header-h)',
      background: 'white',
      borderBottom: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 24px'
    }}>
      <div className="crimson" style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)' }}>
        {getBreadcrumb()}
      </div>
    </div>
  );
};
