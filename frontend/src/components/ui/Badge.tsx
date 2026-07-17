export const Badge = ({ 
  children, 
  variant = 'muted' 
}: { 
  children: React.ReactNode; 
  variant?: 'success' | 'warning' | 'danger' | 'info' | 'gold' | 'muted' | 'navy';
}) => (
  <span className={`badge badge-${variant}`}>
    {children}
  </span>
);
