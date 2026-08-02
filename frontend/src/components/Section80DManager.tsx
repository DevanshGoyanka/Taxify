// Section 80D Health Insurance Manager — CBDT AY 2026-27 COMPLIANT
// Mirrors official Schedule80D JSON schema with 4 policy categories:
//   1. Self & Family (non-senior)       → Sec80DSelfFamHIDtls
//   2. Self & Family (senior citizen)    → Sec80DSelfFamSrCtznHIDtls
//   3. Parents (non-senior)             → Sec80DParentsHIDtls
//   4. Parents (senior citizen)          → Sec80DParentsSrCtznHIDtls
//
// Each category collects Sch80DInsDtls[] (InsurerName, PolicyNo, HealthInsAmt)
// plus preventive health checkup and medical expense for non-insured seniors.
// UI style matches DonationEntryManager: collapsible cards with category badges.

import React, { useState } from 'react';

// ---- Per-policy entry (maps to Sch80DInsDtls) ----
interface Policy80D {
  id: string;
  insurerName: string;    // → InsurerName (max 125, required)
  policyNo: string;       // → PolicyNo (max 75, required)
  premiumAmount: number;  // → HealthInsAmt (required)
  policyType: 'INDIVIDUAL' | 'FAMILY_FLOATER' | 'GROUP' | 'OTHER';
  dateOfCommencement: string;
}

// ---- One 80D "category" (self non-sr, self sr, parents non-sr, parents sr) ----
interface Category80D {
  policies: Policy80D[];
  preventiveCheckup: number;     // max 5000
  medicalExpense: number;        // for non-insured seniors
}

// ---- Top-level 80D form data ----
export interface Section80DData {
  selfSeniorCitizen: 'Y' | 'N' | 'S';
  parentsSeniorCitizen: 'Y' | 'N' | 'P';
  selfFamily: Category80D;
  selfFamilySenior: Category80D;
  parents: Category80D;
  parentsSenior: Category80D;
}

interface Section80DManagerProps {
  data: Section80DData;
  onChange: (data: Section80DData) => void;
  /** Authoritative 80D eligible amount from the backend engine (section_80d). */
  backendEligible?: number | null;
}

// Caps per official schema
const CAP_SELF_FAMILY = 25000;
const CAP_SELF_FAMILY_SR = 50000;
const CAP_PARENTS = 25000;
const CAP_PARENTS_SR = 50000;
const CAP_PREVENTIVE = 5000;

let _policyIdCounter = 1;
const nextPolicyId = (): string => `80d-p-${Date.now()}-${_policyIdCounter++}`;

function sumPremiums(policies: Policy80D[]): number {
  return policies.reduce((s, p) => s + p.premiumAmount, 0);
}

// Category metadata
type CatKey = 'selfFamily' | 'selfFamilySenior' | 'parents' | 'parentsSenior';
interface CatMeta { key: CatKey; label: string; shortLabel: string; color: string; cap: number; }

const CATS: CatMeta[] = [
  { key: 'selfFamily', label: 'Self & Family (Non-Senior)', shortLabel: 'Self/Fam', color: '#1565c0', cap: CAP_SELF_FAMILY },
  { key: 'selfFamilySenior', label: 'Self & Family (Senior Citizen)', shortLabel: 'Self/Sr', color: '#2e7d32', cap: CAP_SELF_FAMILY_SR },
  { key: 'parents', label: 'Parents (Non-Senior)', shortLabel: 'Parents', color: '#ef6c00', cap: CAP_PARENTS },
  { key: 'parentsSenior', label: 'Parents (Senior Citizen)', shortLabel: 'Parents/Sr', color: '#6a1b9a', cap: CAP_PARENTS_SR },
];

// ---- Shared styles ----
const labelStyle: React.CSSProperties = {
  display: 'block', marginBottom: 3, fontSize: 11, fontWeight: 600, color: '#555',
};
const inputStyle: React.CSSProperties = {
  width: '100%', padding: '6px 8px', border: '1px solid #ddd', borderRadius: 4,
  fontSize: 12, boxSizing: 'border-box',
};

export const Section80DManager: React.FC<Section80DManagerProps> = ({ data, onChange, backendEligible }) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const updateCategory = (catKey: CatKey, updater: (cat: Category80D) => Category80D) => {
    onChange({ ...data, [catKey]: updater(data[catKey] as Category80D) });
  };

  const addPolicy = (catKey: CatKey) => {
    const newPolicy: Policy80D = {
      id: nextPolicyId(), insurerName: '', policyNo: '', premiumAmount: 0,
      policyType: 'INDIVIDUAL', dateOfCommencement: '',
    };
    updateCategory(catKey, c => ({ ...c, policies: [...c.policies, newPolicy] }));
    setExpandedId(newPolicy.id);
  };

  const removePolicy = (catKey: CatKey, id: string) => {
    updateCategory(catKey, c => ({ ...c, policies: c.policies.filter(p => p.id !== id) }));
    if (expandedId === id) setExpandedId(null);
  };

  const updatePolicy = (catKey: CatKey, id: string, field: keyof Policy80D, value: unknown) => {
    updateCategory(catKey, c => ({
      ...c, policies: c.policies.map(p => p.id === id ? { ...p, [field]: value } : p),
    }));
  };

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  // Which categories are visible
  const showSelfFamily = data.selfSeniorCitizen !== 'S';
  const showSelfFamilySr = data.selfSeniorCitizen === 'Y';
  const showParents = data.parentsSeniorCitizen !== 'P';
  const showParentsSr = data.parentsSeniorCitizen === 'Y';
  const visibilityMap: Record<CatKey, boolean> = {
    selfFamily: showSelfFamily,
    selfFamilySenior: showSelfFamilySr,
    parents: showParents,
    parentsSenior: showParentsSr,
  };

  // Grand total — DISPLAY ESTIMATE ONLY.
  // The authoritative 80D eligible amount is computed by the backend engine
  // (section_80d.py), which applies the shared ₹5,000 preventive-checkup
  // sub-limit across buckets and the per-bucket caps.  This frontend sum is
  // an indicative estimate for the summary card and must NOT be treated as
  // the final deduction; the backend value from the compute endpoint is the
  // source of truth.
  let totalEligible = 0;
  const caps: Record<CatKey, number> = { selfFamily: CAP_SELF_FAMILY, selfFamilySenior: CAP_SELF_FAMILY_SR, parents: CAP_PARENTS, parentsSenior: CAP_PARENTS_SR };
  for (const cm of CATS) {
    if (!visibilityMap[cm.key]) continue;
    const cat = data[cm.key] as Category80D;
    const prem = sumPremiums(cat.policies);
    const premEligible = Math.min(prem, caps[cm.key]);
    totalEligible += premEligible + Math.min(cat.preventiveCheckup, CAP_PREVENTIVE) + Math.min(cat.medicalExpense, caps[cm.key] - premEligible);
  }

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Schedule 80D — Health Insurance</h3>
          <p style={{ margin: '4px 0 0', fontSize: 11, color: '#666' }}>
            Per-policy details with senior citizen flags. Premiums capped per category. Preventive checkup max ₹5,000.
          </p>
        </div>
      </div>

      {/* Senior citizen flags */}
      <div style={{ display: 'flex', gap: 20, marginBottom: 16, flexWrap: 'wrap' }}>
        <div>
          <label style={labelStyle}>Self / Family *</label>
          <select value={data.selfSeniorCitizen}
            onChange={e => onChange({ ...data, selfSeniorCitizen: e.target.value as 'Y' | 'N' | 'S' })}
            style={inputStyle}>
            <option value="N">Non-Senior Citizen (cap ₹25,000)</option>
            <option value="Y">Senior Citizen (cap ₹50,000)</option>
            <option value="S">Not claiming for Self/Family</option>
          </select>
        </div>
        <div>
          <label style={labelStyle}>Parents *</label>
          <select value={data.parentsSeniorCitizen}
            onChange={e => onChange({ ...data, parentsSeniorCitizen: e.target.value as 'Y' | 'N' | 'P' })}
            style={inputStyle}>
            <option value="N">Non-Senior Citizen (cap ₹25,000)</option>
            <option value="Y">Senior Citizen (cap ₹50,000)</option>
            <option value="P">Not claiming for Parents</option>
          </select>
        </div>
      </div>

      {/* Category summary cards (only visible ones) */}
      {(CATS.some(cm => visibilityMap[cm.key] && ((data[cm.key] as Category80D).policies.length > 0 || (data[cm.key] as Category80D).preventiveCheckup > 0 || (data[cm.key] as Category80D).medicalExpense > 0)) ) && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10, marginBottom: 16 }}>
          {CATS.filter(cm => visibilityMap[cm.key]).map(cm => {
            const cat = data[cm.key] as Category80D;
            const prem = sumPremiums(cat.policies);
            const premEligible = Math.min(prem, cm.cap);
            const prevEligible = Math.min(cat.preventiveCheckup, CAP_PREVENTIVE);
            const total = premEligible + prevEligible + Math.min(cat.medicalExpense, cm.cap - premEligible);
            if (prem === 0 && cat.preventiveCheckup === 0 && cat.medicalExpense === 0) return null;
            return (
              <div key={cm.key} style={{ padding: 10, borderRadius: 6, border: `1px solid ${cm.color}30`, background: `${cm.color}08` }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: cm.color, marginBottom: 4 }}>{cm.shortLabel}</div>
                <div style={{ fontSize: 12, color: '#333' }}>Premium: <strong>₹{prem.toLocaleString('en-IN')}</strong></div>
                <div style={{ fontSize: 12, color: cm.color }}>Eligible: <strong>₹{total.toLocaleString('en-IN')}</strong></div>
                <div style={{ fontSize: 10, color: '#888' }}>Policies: {cat.policies.length}</div>
              </div>
            );
          })}
        </div>
      )}

      {/* Policy cards per category */}
      {CATS.filter(cm => visibilityMap[cm.key]).map(cm => {
        const cat = data[cm.key] as Category80D;
        const prem = sumPremiums(cat.policies);
        const premEligible = Math.min(prem, cm.cap);
        const prevEligible = Math.min(cat.preventiveCheckup, CAP_PREVENTIVE);
        const medEligible = Math.min(cat.medicalExpense, cm.cap - premEligible);

        return (
          <div key={cm.key} style={{ marginBottom: 16 }}>
            {/* Category header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ background: cm.color, color: 'white', fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 3 }}>
                  {cm.shortLabel}
                </span>
                <span style={{ fontSize: 13, fontWeight: 600 }}>{cm.label}</span>
                <span style={{ fontSize: 11, color: '#888' }}>Cap: ₹{cm.cap.toLocaleString('en-IN')}</span>
              </div>
              <button onClick={() => addPolicy(cm.key)} style={{
                background: cm.color, color: 'white', border: 'none', padding: '6px 12px', borderRadius: 4, cursor: 'pointer', fontSize: 12, fontWeight: 600,
              }}>
                + Add Policy
              </button>
            </div>

            {/* Empty state */}
            {cat.policies.length === 0 && cat.preventiveCheckup === 0 && cat.medicalExpense === 0 && (
              <div style={{ textAlign: 'center', padding: 20, color: '#999', background: '#fafafa', borderRadius: 8, border: '1px dashed #ddd', marginBottom: 8 }}>
                No health insurance policies added.
              </div>
            )}

            {/* Per-policy collapsible cards */}
            {cat.policies.map((p) => {
              const isExpanded = expandedId === p.id;
              return (
                <div key={p.id} style={{
                  background: 'white', border: `1px solid ${isExpanded ? cm.color : '#e0e0e0'}`,
                  borderLeft: `4px solid ${cm.color}`, borderRadius: 6, marginBottom: 6, overflow: 'hidden',
                }}>
                  {/* Collapsed summary */}
                  <div onClick={() => toggleExpand(p.id)} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '8px 12px', cursor: 'pointer', userSelect: 'none',
                    background: isExpanded ? `${cm.color}06` : 'white',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0 }}>
                      <span style={{ fontSize: 13, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {p.insurerName || '(Unnamed Insurer)'}
                      </span>
                      {p.policyNo && <span style={{ fontSize: 11, color: '#888', fontFamily: 'monospace' }}>Policy: {p.policyNo}</span>}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
                      <span style={{ fontSize: 13, fontWeight: 600 }}>₹{p.premiumAmount.toLocaleString('en-IN')}</span>
                      <span style={{ fontSize: 14, color: '#999', transform: isExpanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>▾</span>
                      <button onClick={(ev) => { ev.stopPropagation(); removePolicy(cm.key, p.id); }} style={{
                        background: 'transparent', border: 'none', color: '#f44336', fontSize: 16, cursor: 'pointer', padding: '0 2px', lineHeight: 1,
                      }} title="Remove policy">×</button>
                    </div>
                  </div>

                  {/* Expanded detail */}
                  {isExpanded && (
                    <div style={{ padding: '12px 14px', borderTop: '1px solid #eee' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
                        <div>
                          <label style={labelStyle}>Insurer Name *</label>
                          <input type="text" value={p.insurerName} onChange={e => updatePolicy(cm.key, p.id, 'insurerName', e.target.value)}
                            placeholder="e.g., Star Health, ICICI Lombard" maxLength={125} style={inputStyle} />
                        </div>
                        <div>
                          <label style={labelStyle}>Policy Number *</label>
                          <input type="text" value={p.policyNo} onChange={e => updatePolicy(cm.key, p.id, 'policyNo', e.target.value)}
                            placeholder="Policy number" maxLength={75} style={inputStyle} />
                        </div>
                        <div>
                          <label style={labelStyle}>Premium Amount (₹) *</label>
                          <input type="number" value={p.premiumAmount || ''} onChange={e => updatePolicy(cm.key, p.id, 'premiumAmount', parseFloat(e.target.value) || 0)}
                            placeholder="0" min={0} style={{ ...inputStyle, fontWeight: 600 }} />
                        </div>
                        <div>
                          <label style={labelStyle}>Policy Type *</label>
                          <select value={p.policyType || 'INDIVIDUAL'} onChange={e => updatePolicy(cm.key, p.id, 'policyType', e.target.value)} style={inputStyle}>
                            <option value="INDIVIDUAL">Individual</option>
                            <option value="FAMILY_FLOATER">Family Floater</option>
                            <option value="GROUP">Group Policy</option>
                            <option value="OTHER">Other</option>
                          </select>
                        </div>
                        <div>
                          <label style={labelStyle}>Date of Commencement *</label>
                          <input type="date" value={p.dateOfCommencement || ''} onChange={e => updatePolicy(cm.key, p.id, 'dateOfCommencement', e.target.value)} style={inputStyle} />
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}

            {/* Preventive checkup + Medical expense */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10, marginTop: 8, padding: '0 2px' }}>
              <div>
                <label style={labelStyle}>Preventive Health Checkup (max ₹5,000)</label>
                <input type="number" value={cat.preventiveCheckup || ''} min={0} max={CAP_PREVENTIVE}
                  onChange={e => updateCategory(cm.key, c => ({ ...c, preventiveCheckup: parseFloat(e.target.value) || 0 }))}
                  style={inputStyle} />
              </div>
              {cm.key === 'selfFamilySenior' || cm.key === 'parentsSenior' ? (
                <div>
                  <label style={labelStyle}>Medical Expense (non-insured seniors)</label>
                  <input type="number" value={cat.medicalExpense || ''} min={0}
                    onChange={e => updateCategory(cm.key, c => ({ ...c, medicalExpense: parseFloat(e.target.value) || 0 }))}
                    style={inputStyle} />
                </div>
              ) : null}
            </div>

            {/* Category subtotal */}
            {(prem > 0 || cat.preventiveCheckup > 0 || cat.medicalExpense > 0) && (
              <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid #eee', display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '0 2px' }}>
                <span style={{ color: '#666' }}>Premium: ₹{prem.toLocaleString('en-IN')} | Preventive: ₹{prevEligible.toLocaleString('en-IN')}</span>
                <span style={{ fontWeight: 600, color: cm.color }}>Eligible: ₹{(premEligible + prevEligible + medEligible).toLocaleString('en-IN')}</span>
              </div>
            )}
          </div>
        );
      })}

      {/* Grand total footer — displays the authoritative backend-computed
          80D eligible amount. When the backend result is not yet available
          (e.g., no data entered), the footer is hidden. The frontend never
          computes the statutory eligible amount itself. */}
      {((backendEligible ?? 0) > 0 || CATS.some(cm => visibilityMap[cm.key] && (data[cm.key] as Category80D).policies.length > 0)) && (
        <div style={{
          marginTop: 14, padding: 12, background: '#e8eaf6', borderRadius: 6,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span style={{ fontWeight: 600, fontSize: 13 }}>Total 80D Eligible Deduction {backendEligible == null ? '(estimate — backend not yet computed)' : ''}</span>
          <span style={{ fontWeight: 700, fontSize: 16, color: '#2e7d32' }}>₹{(backendEligible ?? totalEligible).toLocaleString('en-IN')}</span>
        </div>
      )}
    </div>
  );
};
