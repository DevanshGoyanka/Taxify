import { useLocation } from 'react-router-dom';

export const Topbar = () => {
  const location = useLocation();
  const isClientManager = location.pathname === '/clients';
  const isOpenItr = location.pathname.startsWith('/filing/');
  const isClientWorkspace = isClientManager || isOpenItr;
  const pageName = location.pathname === '/dashboard' ? 'Dashboard' : isClientWorkspace ? 'Client Manager' : 'Help';

  return (
    <header className={`topbar${isClientManager ? ' topbar-client-manager' : ''}`}>
      <span className="topbar-page-icon" aria-hidden="true">{isClientManager ? '◉' : '⌂'}</span>
      <span className="topbar-page-name">{pageName}</span>
      <span className="topbar-help" aria-label="Help">ⓘ&nbsp; Help</span>
    </header>
  );
};
