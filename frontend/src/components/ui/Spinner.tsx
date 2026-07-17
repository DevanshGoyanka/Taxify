export const Spinner = ({ size = 20 }: { size?: number }) => (
  <div style={{
    width: size, height: size,
    border: `2px solid var(--border)`,
    borderTopColor: `var(--gold)`,
    borderRadius: '50%',
    animation: 'spin 0.8s linear infinite',
    display: 'inline-block',
  }} />
);
