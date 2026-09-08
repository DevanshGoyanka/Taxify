import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import clientsIcon from '../../../svgs/clients.svg';
import taxifyWhiteLogo from '../../../svgs/taxify white.png';
import taxifyWhiteCroppedLogo from '../../assets/taxify-white-cropped.png';
import { tokenManager } from '../../api/tokenManager';
import { ADVANCED_TAX_CALCULATORS } from '../../pages/AdvancedTaxPage';

type MenuItemProps = {
  label: string;
  icon: string;
  path?: string;
  disabled?: boolean;
  collapsed?: boolean;
};

const MenuItem = ({ label, icon, path, disabled = false, collapsed = false }: MenuItemProps) => {
  const location = useLocation();
  const active = Boolean(path && (location.pathname === path || location.pathname.startsWith(`${path}/`)));
  const content = (
    <>
      <span className="sidebar-item-icon" aria-hidden="true">{icon}</span>
      {!collapsed && <span>{label}</span>}
    </>
  );

  if (!path || disabled) {
    return (
      <div
        className={`sidebar-item${disabled ? ' sidebar-item-disabled' : ''}${collapsed ? ' sidebar-item-collapsed' : ''}`}
        title={collapsed ? label : undefined}
      >
        {content}
      </div>
    );
  }

  return (
    <Link
      className={`sidebar-item${active ? ' sidebar-item-active' : ''}${collapsed ? ' sidebar-item-collapsed' : ''}`}
      to={path}
      title={collapsed ? label : undefined}
    >
      {content}
    </Link>
  );
};

type SidebarProps = {
  collapsed: boolean;
  onToggleCollapse: () => void;
};

export const Sidebar = ({ collapsed, onToggleCollapse }: SidebarProps) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [clientsOpen, setClientsOpen] = useState(true);
  const [toolsOpen, setToolsOpen] = useState(true);
  const [advancedToolsOpen, setAdvancedToolsOpen] = useState(false);
  const email = tokenManager.getEmail() || 'User';
  const initial = email[0]?.toUpperCase() || 'U';
  const advancedTaxActive = location.pathname.startsWith('/advanced-tax');

  const handleLogout = (): void => {
    tokenManager.clear();
    navigate('/login');
  };

  return (
    <aside
      className={`sidebar${collapsed ? ' sidebar-collapsed' : ''}`}
      aria-label="Main navigation"
    >
      <div className={`sidebar-header${collapsed ? ' sidebar-header-collapsed' : ''}`}>
        {collapsed ? (
          <Link to="/dashboard" className="sidebar-brand" aria-label="Taxify dashboard">
            <img src={taxifyWhiteCroppedLogo} alt="Taxify" className="sidebar-brand-logo sidebar-brand-logo-collapsed" />
          </Link>
        ) : (
          <>
            <Link to="/dashboard" className="sidebar-brand" aria-label="Taxify dashboard">
              <img src={taxifyWhiteLogo} alt="Taxify" className="sidebar-brand-logo" />
            </Link>
            <button
              type="button"
              className="sidebar-collapse-toggle"
              onClick={onToggleCollapse}
              aria-label="Collapse sidebar"
              aria-expanded={true}
              title="Collapse sidebar"
            >
              <span className="sidebar-hamburger" aria-hidden="true">
                <span /><span /><span />
              </span>
            </button>
          </>
        )}
      </div>

      {!collapsed && (
        <div className="sidebar-search" role="search">
          <span aria-hidden="true">⌕</span>
          <input type="search" placeholder="Search" aria-label="Search" />
          <kbd>CTRL</kbd><kbd>K</kbd>
        </div>
      )}

      <nav className="sidebar-nav">
        <MenuItem label="Dashboard" icon="⌂" path="/dashboard" collapsed={collapsed} />

        <button
          className={`sidebar-section-toggle${collapsed ? ' sidebar-section-toggle-collapsed' : ''}`}
          type="button"
          onClick={() => setClientsOpen((open) => !open)}
          title={collapsed ? 'Clients' : undefined}
          aria-label="Clients"
        >
          <span className="sidebar-section-toggle-label">
            <img className="sidebar-svg-icon sidebar-client-icon" alt="" src={clientsIcon} />
            {!collapsed && <span>Clients</span>}
          </span>
          {!collapsed && <span aria-hidden="true">{clientsOpen ? '⌄' : '›'}</span>}
        </button>
        {!collapsed && clientsOpen && (
          <div className="sidebar-submenu">
            <MenuItem label="Client Manager" icon="◉" path="/clients" />
            <MenuItem label="ITR Filing" icon="▤" disabled />
          </div>
        )}
        {collapsed && (
          <MenuItem label="Client Manager" icon="◉" path="/clients" collapsed />
        )}

        <button
          className={`sidebar-section-toggle${collapsed ? ' sidebar-section-toggle-collapsed' : ''}`}
          type="button"
          onClick={() => setToolsOpen((open) => !open)}
          title={collapsed ? 'Tools' : undefined}
          aria-label="Tools"
        >
          <span className="sidebar-section-toggle-label">
            <span className="sidebar-item-icon" aria-hidden="true">⚙</span>
            {!collapsed && <span>Tools</span>}
          </span>
          {!collapsed && <span aria-hidden="true">{toolsOpen ? '⌄' : '›'}</span>}
        </button>
        {!collapsed && toolsOpen && (
          <div className="sidebar-submenu">
            <div className="sidebar-flyout-wrap" onMouseEnter={() => setAdvancedToolsOpen(true)} onMouseLeave={() => setAdvancedToolsOpen(false)}>
              <Link className={`sidebar-item${advancedTaxActive ? ' sidebar-item-active' : ''}`} to="/advanced-tax/hra" onFocus={() => setAdvancedToolsOpen(true)}>
                <span className="sidebar-item-icon" aria-hidden="true">▦</span>
                <span>Advanced Tax Tools</span>
                <span className="sidebar-flyout-arrow" aria-hidden="true">›</span>
              </Link>
              {advancedToolsOpen && (
                <div className="sidebar-flyout" aria-label="Advanced tax calculators">
                  {ADVANCED_TAX_CALCULATORS.map((calculator) => (
                    <Link
                      key={calculator.id}
                      className={`sidebar-item${location.pathname === `/advanced-tax/${calculator.id}` ? ' sidebar-item-active' : ''}`}
                      to={`/advanced-tax/${calculator.id}`}
                    >
                      <span className="sidebar-item-icon" aria-hidden="true">{calculator.icon}</span>
                      <span>{calculator.name}</span>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
        {collapsed && (
          <MenuItem label="Advanced Tax Tools" icon="▦" path="/advanced-tax/hra" collapsed />
        )}
      </nav>

      <div className={`sidebar-footer${collapsed ? ' sidebar-footer-collapsed' : ''}`}>
        <div className="sidebar-user-avatar" title={collapsed ? email : undefined}>{initial}</div>
        {!collapsed && (
          <div className="sidebar-user-details">
            <strong>{email}</strong>
            <span>Administrator</span>
          </div>
        )}
        <button
          className="sidebar-logout"
          type="button"
          onClick={handleLogout}
          title="Log out"
          aria-label="Log out"
        >↪</button>
      </div>
    </aside>
  );
};
