import React, { useState } from 'react';
import eyeOpenIcon from '../../../svgs/eye-open.svg';
import eyeCloseIcon from '../../../svgs/eye-close.svg';

interface CollapsibleWarningProps {
  children: React.ReactNode;
  title?: string;
  defaultOpen?: boolean;
}

export function CollapsibleWarning({ children, title, defaultOpen = true }: CollapsibleWarningProps) {
  const [open, setOpen] = useState<boolean>(defaultOpen);

  return (
    <div
      style={{
        marginBottom: 16,
        display: 'flex',
        justifyContent: 'flex-end',
        alignItems: 'flex-start',
        ...(open
          ? {
              padding: '14px 16px',
              background: '#fdecec',
              border: '1px solid #fcd34d',
              borderRadius: 8,
              fontSize: 13,
              color: '#92400e',
            }
          : { padding: 0, background: 'transparent', border: 'none' }),
      }}
    >
      {open && (
        <div style={{ flex: 1, minWidth: 0 }}>
          {title && <strong style={{ fontSize: 14, display: 'block', marginBottom: 4 }}>{title}</strong>}
          <div>{children}</div>
        </div>
      )}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? 'Hide warning' : 'Show warning'}
        title={open ? 'Hide' : 'Show'}
        style={{
          flex: '0 0 auto',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          width: 22,
          height: 22,
          padding: 0,
          marginLeft: open ? 8 : 0,
        }}
      >
        <img
          src={open ? eyeCloseIcon : eyeOpenIcon}
          alt={open ? 'Hide' : 'Show'}
          style={{ width: 20, height: 20, display: 'block' }}
        />
      </button>
    </div>
  );
}
