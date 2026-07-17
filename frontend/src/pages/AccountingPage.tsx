export default function AccountingPage() {
  return (
    <div>
      <h1 className="crimson" style={{ fontSize: 22, marginBottom: 24 }}>Firm Accounting</h1>
      <div style={{ background: 'var(--warning-bg)', padding: 16, borderRadius: 'var(--radius)', marginBottom: 24, border: '1px solid var(--warning)' }}>
        🚧 Backend integration coming soon
      </div>
      <div style={{ background: 'white', padding: 24, borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Income & Expense Summary</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
          <div><div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Total Income</div><div className="mono" style={{ fontSize: 24, fontWeight: 600, color: 'var(--success)' }}>₹18,50,000</div></div>
          <div><div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Total Expenses</div><div className="mono" style={{ fontSize: 24, fontWeight: 600, color: 'var(--danger)' }}>₹6,20,000</div></div>
        </div>
      </div>
    </div>
  );
}
