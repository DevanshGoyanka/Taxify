import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

export const AppLayout = () => {
  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar />
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        marginLeft: 'var(--sidebar-w)'
      }}>
        <Topbar />
        <main style={{
          flex: 1,
          overflowY: 'auto',
          padding: 24,
          background: 'var(--bg)'
        }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
};
