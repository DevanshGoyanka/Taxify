import { useLocation } from 'react-router-dom';

type TopbarProps = {
  collapsed: boolean;
  onToggleCollapse: () => void;
};

export const Topbar = ({ collapsed, onToggleCollapse }: TopbarProps) => {
  const location = useLocation();
  const isClientManager = location.pathname === '/clients';
  const isOpenItr = location.pathname.startsWith('/filing/');
  const isClientWorkspace = isClientManager || isOpenItr;
  const pageName = location.pathname === '/dashboard' ? 'Dashboard' : isClientWorkspace ? 'Client Manager' : 'Help';

  return (
    <header className={`topbar${isClientManager ? ' topbar-client-manager' : ''}`}>
      {collapsed && (
        <button
          type="button"
          className="topbar-collapse-toggle"
          onClick={onToggleCollapse}
          aria-label="Expand sidebar"
          aria-expanded={false}
          title="Expand sidebar"
        >
          <span className="topbar-hamburger" aria-hidden="true">
            <span /><span /><span />
          </span>
        </button>
      )}
      <span className="topbar-page-icon" aria-hidden="true">{isClientManager ? '◉' : '⌂'}</span>
      <span className="topbar-page-name">{pageName}</span>
      <span className="topbar-help" aria-label="Help">ⓘ&nbsp; Help</span>
    </header>
  );
};
