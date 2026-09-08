import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

export const AppLayout = () => {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className={`app-shell${collapsed ? ' app-shell-sidebar-collapsed' : ''}`}>
      <Sidebar collapsed={collapsed} onToggleCollapse={() => setCollapsed((value) => !value)} />
      <div className="app-content">
        <Topbar collapsed={collapsed} onToggleCollapse={() => setCollapsed((value) => !value)} />
        <main className="app-main">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
