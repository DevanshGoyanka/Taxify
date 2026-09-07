export const Badge = ({
  children,
  variant = 'muted',
  className = ''
}: {
  children: React.ReactNode;
  variant?: 'success' | 'warning' | 'danger' | 'info' | 'gold' | 'muted' | 'navy';
  className?: string;
}) => (
  <span className={`badge badge-${variant}${className ? ` ${className}` : ''}`}>
    {children}
  </span>
);
