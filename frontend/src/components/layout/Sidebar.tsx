import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import clientsIcon from '../../../svgs/clients.svg';
import taxifyWhiteLogo from '../../../svgs/taxify white.png';
import { tokenManager } from '../../api/tokenManager';
import { ADVANCED_TAX_CALCULATORS } from '../../pages/AdvancedTaxPage';

type MenuItemProps = {
  label: string;
  icon: string;
  path?: string;
  disabled?: boolean;
};

const MenuItem = ({ label, icon, path, disabled = false }: MenuItemProps) => {
  const location = useLocation();
  const active = Boolean(path && (location.pathname === path || location.pathname.startsWith(`${path}/`)));
  const content = (
    <>
      <span className="sidebar-item-icon" aria-hidden="true">{icon}</span>
      <span>{label}</span>
    </>
  );

  if (!path || disabled) {
    return <div className={`sidebar-item${disabled ? ' sidebar-item-disabled' : ''}`}>{content}</div>;
  }

  return <Link className={`sidebar-item${active ? ' sidebar-item-active' : ''}`} to={path}>{content}</Link>;
};

export const Sidebar = () => {
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
    <aside className="sidebar" aria-label="Main navigation">
      <div className="sidebar-header">
        <Link to="/dashboard" className="sidebar-brand" aria-label="Taxify dashboard">
          <img src={taxifyWhiteLogo} alt="Taxify" className="sidebar-brand-logo" />
        </Link>
      </div>

      <div className="sidebar-search" role="search">
        <span aria-hidden="true">⌕</span>
        <input type="search" placeholder="Search" aria-label="Search" />
        <kbd>CTRL</kbd><kbd>K</kbd>
      </div>

      <nav className="sidebar-nav">
        <MenuItem label="Dashboard" icon="⌂" path="/dashboard" />

        <button className="sidebar-section-toggle" type="button" onClick={() => setClientsOpen((open) => !open)}>
          <span><img className="sidebar-svg-icon sidebar-client-icon" src={clientsIcon} alt="" />Clients</span>
          <span aria-hidden="true">{clientsOpen ? '⌄' : '›'}</span>
        </button>
        {clientsOpen && (
          <div className="sidebar-submenu">
            <MenuItem label="Client Manager" icon="◉" path="/clients" />
            <MenuItem label="ITR Filing" icon="▤" disabled />
          </div>
        )}

        <button className="sidebar-section-toggle" type="button" onClick={() => setToolsOpen((open) => !open)}>
          <span><span className="sidebar-item-icon" aria-hidden="true">⚙</span>Tools</span>
          <span aria-hidden="true">{toolsOpen ? '⌄' : '›'}</span>
        </button>
        {toolsOpen && (
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
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-user-avatar">{initial}</div>
        <div className="sidebar-user-details">
          <strong>{email}</strong>
          <span>Administrator</span>
        </div>
        <button className="sidebar-logout" type="button" onClick={handleLogout} title="Log out">↪</button>
      </div>
    </aside>
  );
};
