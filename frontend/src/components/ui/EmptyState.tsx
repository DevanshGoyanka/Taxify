export const EmptyState = ({ message }: { message: string }) => (
  <div style={{
    textAlign: 'center',
    padding: '48px 24px',
    color: 'var(--text-muted)',
  }}>
    <div style={{ fontSize: 48, marginBottom: 16 }}>📭</div>
    <div>{message}</div>
  </div>
);
