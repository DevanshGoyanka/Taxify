// Section 80D Health Insurance Manager — CBDT AY 2026-27 COMPLIANT
// Mirrors the official Schedule80D JSON schema with 4 policy categories:
//   1. Self & Family (non-senior)              → Sec80DSelfFamHIDtls
//   2. Self & Family (senior citizen)          → Sec80DSelfFamSrCtznHIDtls
//   3. Parents (non-senior)                    → Sec80DParentsHIDtls
//   4. Parents (senior citizen)                → Sec80DParentsSrCtznHIDtls
//
// Each category collects Sch80DInsDtls[] (InsurerName, PolicyNo, HealthInsAmt)
// plus preventive health checkup and medical expense for non-insured seniors.

import React, { useState, useMemo } from 'react';

// ---- Per-policy entry (maps to Sch80DInsDtls) ----
interface Policy80D {
  id: string;
  insurerName: string;    // max 125
  policyNo: string;       // max 75
  premiumAmount: number;  // → HealthInsAmt
}

// ---- One 80D "category" (self non-sr, self sr, parents non-sr, parents sr) ----
interface Category80D {
  policies: Policy80D[];
  preventiveCheckup: number;     // max 5000
  medicalExpense: number;        // for non-insured seniors (not capped)
}

// ---- Top-level 80D form data ----
export interface Section80DData {
  // Senior citizen flags
  selfSeniorCitizen: 'Y' | 'N' | 'S';     // Y=senior self, N=non-senior, S=not claiming
  parentsSeniorCitizen: 'Y' | 'N' | 'P';  // Y=senior parents, N=non-senior, P=not claiming
  // 4 categories
  selfFamily: Category80D;
  selfFamilySenior: Category80D;
  parents: Category80D;
  parentsSenior: Category80D;
}

interface Section80DManagerProps {
  data: Section80DData;
  onChange: (data: Section80DData) => void;
}

// Caps per official schema
const CAP_SELF_FAMILY = 25000;
const CAP_SELF_FAMILY_SR = 50000;
const CAP_PARENTS = 25000;
const CAP_PARENTS_SR = 50000;
const CAP_PREVENTIVE = 5000;

let _policyIdCounter = 1;
const nextPolicyId = (): string => `80d-p-${Date.now()}-${_policyIdCounter++}`;

const newCategory = (): Category80D => ({ policies: [], preventiveCheckup: 0, medicalExpense: 0 });

function sumPremiums(policies: Policy80D[]): number {
  return policies.reduce((s, p) => s + p.premiumAmount, 0);
}

export const Section80DManager: React.FC<Section80DManagerProps> = ({ data, onChange }) => {

  // Update a specific category
  const updateCategory = (catKey: keyof Section80DData, updater: (cat: Category80D) => Category80D) => {
    if (catKey === 'selfSeniorCitizen' || catKey === 'parentsSeniorCitizen') return;
    onChange({ ...data, [catKey]: updater(data[catKey] as Category80D) });
  };

  // ---- Category summary per policy display card ----
  const CategoryCard = ({
    title, color, catKey, cap, srFlag, isVisible,
  }: {
    title: string; color: string; catKey: 'selfFamily' | 'selfFamilySenior' | 'parents' | 'parentsSenior';
    cap: number; srFlag: 'Y' | 'N' | 'S' | 'P'; isVisible: boolean;
  }) => {
    if (!isVisible) return null;
    const cat = data[catKey] as Category80D;
    const premiumTotal = sumPremiums(cat.policies);
    const eligible = Math.min(premiumTotal, cap);
    const totalClaim = eligible + Math.min(cat.preventiveCheckup, CAP_PREVENTIVE) + Math.min(cat.medicalExpense, cap - eligible);

    return (
      <div style={{ marginBottom: 16, background: 'white', borderRadius: 8, border: `1px solid ${color}30`, borderLeft: `4px solid ${color}`, overflow: 'hidden' }}>
        {/* Card header */}
        <div style={{ padding: '10px 14px', background: `${color}08`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <span style={{ fontWeight: 600, fontSize: 13, color }}>{title}</span>
            <span style={{ fontSize: 10, color: '#888', marginLeft: 8 }}>Cap: ₹{cap.toLocaleString('en-IN')}</span>
          </div>
        </div>

        <div style={{ padding: '12px 14px' }}>
          {/* Policy table */}
          {cat.policies.length === 0 ? (
            <div style={{ fontSize: 12, color: '#999', padding: '8px 0', textAlign: 'center' }}>
              No policies added. Click + to add health insurance policies.
            </div>
          ) : (
            <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse', marginBottom: 10 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #eee' }}>
                  <th style={{ textAlign: 'left', padding: '4px 8px', fontWeight: 600, color: '#666' }}>Insurer</th>
                  <th style={{ textAlign: 'left', padding: '4px 8px', fontWeight: 600, color: '#666' }}>Policy No.</th>
                  <th style={{ textAlign: 'right', padding: '4px 8px', fontWeight: 600, color: '#666' }}>Premium (₹)</th>
                  <th style={{ width: 30 }}></th>
                </tr>
              </thead>
              <tbody>
                {cat.policies.map((p) => (
                  <tr key={p.id} style={{ borderBottom: '1px solid #f5f5f5' }}>
                    <td style={{ padding: '4px 8px' }}>
                      <input
                        value={p.insurerName}
                        onChange={e => updateCategory(catKey, c => ({
                          ...c, policies: c.policies.map(pp => pp.id === p.id ? { ...pp, insurerName: e.target.value } : pp),
                        }))}
                        placeholder="Insurer name"
                        maxLength={125}
                        style={inlineInputStyle}
                      />
                    </td>
                    <td style={{ padding: '4px 8px' }}>
                      <input
                        value={p.policyNo}
                        onChange={e => updateCategory(catKey, c => ({
                          ...c, policies: c.policies.map(pp => pp.id === p.id ? { ...pp, policyNo: e.target.value } : pp),
                        }))}
                        placeholder="Policy number"
                        maxLength={75}
                        style={inlineInputStyle}
                      />
                    </td>
                    <td style={{ padding: '4px 8px' }}>
                      <input
                        type="number"
                        value={p.premiumAmount || ''}
                        onChange={e => updateCategory(catKey, c => ({
                          ...c, policies: c.policies.map(pp => pp.id === p.id ? { ...pp, premiumAmount: parseFloat(e.target.value) || 0 } : pp),
                        }))}
                        placeholder="0"
                        min={0}
                        style={{ ...inlineInputStyle, textAlign: 'right', width: 100 }}
                      />
                    </td>
                    <td style={{ padding: '4px 4px', textAlign: 'center' }}>
                      <button onClick={() => updateCategory(catKey, c => ({
                        ...c, policies: c.policies.filter(pp => pp.id !== p.id),
                      }))} style={{ background: 'none', border: 'none', color: '#f44336', cursor: 'pointer', fontSize: 14 }}>×</button>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr style={{ borderTop: '2px solid #eee', fontWeight: 600 }}>
                  <td colSpan={2} style={{ padding: '6px 8px', textAlign: 'right', fontSize: 11, color: '#666' }}>Total Premium:</td>
                  <td style={{ padding: '6px 8px', textAlign: 'right', fontSize: 13 }}>₹{premiumTotal.toLocaleString('en-IN')}</td>
                  <td></td>
                </tr>
              </tfoot>
            </table>
          )}

          <button
            onClick={() => updateCategory(catKey, c => ({
              ...c, policies: [...c.policies, { id: nextPolicyId(), insurerName: '', policyNo: '', premiumAmount: 0 }],
            }))}
            style={{ fontSize: 11, background: 'transparent', border: `1px dashed ${color}`, color, borderRadius: 4, padding: '4px 10px', cursor: 'pointer', marginBottom: 8 }}
          >
            + Add Policy
          </button>

          {/* Preventive + Medical */}
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 4 }}>
            <div style={{ flex: '1 1 180px' }}>
              <label style={{ fontSize: 11, color: '#888', display: 'block', marginBottom: 2 }}>Preventive Checkup (max ₹5,000)</label>
              <input type="number" value={cat.preventiveCheckup || ''} min={0} max={CAP_PREVENTIVE}
                onChange={e => updateCategory(catKey, c => ({ ...c, preventiveCheckup: parseFloat(e.target.value) || 0 }))}
                style={{ ...inlineInputStyle, width: '100%' }} />
            </div>
            {srFlag === 'Y' && (
              <div style={{ flex: '1 1 180px' }}>
                <label style={{ fontSize: 11, color: '#888', display: 'block', marginBottom: 2 }}>Medical Expense (non-insured seniors)</label>
                <input type="number" value={cat.medicalExpense || ''} min={0}
                  onChange={e => updateCategory(catKey, c => ({ ...c, medicalExpense: parseFloat(e.target.value) || 0 }))}
                  style={{ ...inlineInputStyle, width: '100%' }} />
              </div>
            )}
          </div>

          {/* Summary per category */}
          <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid #eee', display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
            <span style={{ color: '#666' }}>Premium: ₹{premiumTotal.toLocaleString('en-IN')}</span>
            <span style={{ fontWeight: 600, color }}>Eligible: ₹{totalClaim.toLocaleString('en-IN')}</span>
          </div>
        </div>
      </div>
    );
  };

  // ---- Derived flags ----
  const showSelfFamily = data.selfSeniorCitizen !== 'S';
  const showSelfFamilySr = data.selfSeniorCitizen === 'Y';
  const showParents = data.parentsSeniorCitizen !== 'P';
  const showParentsSr = data.parentsSeniorCitizen === 'Y';

  // Totals
  const totalEligible = useMemo(() => {
    let total = 0;
    if (showSelfFamily) {
      const cat = data.selfFamily;
      const prem = sumPremiums(cat.policies);
      total += Math.min(prem, CAP_SELF_FAMILY) + Math.min(cat.preventiveCheckup, CAP_PREVENTIVE);
    }
    if (showSelfFamilySr) {
      const cat = data.selfFamilySenior;
      const prem = sumPremiums(cat.policies);
      total += Math.min(prem, CAP_SELF_FAMILY_SR) + Math.min(cat.preventiveCheckup, CAP_PREVENTIVE) + Math.min(cat.medicalExpense, CAP_SELF_FAMILY_SR - Math.min(prem, CAP_SELF_FAMILY_SR));
    }
    if (showParents) {
      const cat = data.parents;
      const prem = sumPremiums(cat.policies);
      total += Math.min(prem, CAP_PARENTS) + Math.min(cat.preventiveCheckup, CAP_PREVENTIVE);
    }
    if (showParentsSr) {
      const cat = data.parentsSenior;
      const prem = sumPremiums(cat.policies);
      total += Math.min(prem, CAP_PARENTS_SR) + Math.min(cat.preventiveCheckup, CAP_PREVENTIVE) + Math.min(cat.medicalExpense, CAP_PARENTS_SR - Math.min(prem, CAP_PARENTS_SR));
    }
    return total;
  }, [data]);

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Section 80D — Health Insurance</h3>
        <p style={{ margin: '4px 0 0', fontSize: 11, color: '#666' }}>
          Add per-policy details. Premiums capped at applicable limits. Preventive checkup max ₹5,000 per category.
        </p>
      </div>

      {/* Senior citizen flags */}
      <div style={{ display: 'flex', gap: 20, marginBottom: 16, flexWrap: 'wrap' }}>
        <div>
          <label style={{ fontSize: 11, fontWeight: 600, display: 'block', marginBottom: 4 }}>Self / Family *</label>
          <select value={data.selfSeniorCitizen}
            onChange={e => onChange({ ...data, selfSeniorCitizen: e.target.value as 'Y' | 'N' | 'S' })}
            style={{ padding: '6px 10px', border: '1px solid #ddd', borderRadius: 4, fontSize: 12 }}>
            <option value="N">Non-Senior Citizen (cap ₹25,000)</option>
            <option value="Y">Senior Citizen (cap ₹50,000)</option>
            <option value="S">Not claiming for Self/Family</option>
          </select>
        </div>
        <div>
          <label style={{ fontSize: 11, fontWeight: 600, display: 'block', marginBottom: 4 }}>Parents *</label>
          <select value={data.parentsSeniorCitizen}
            onChange={e => onChange({ ...data, parentsSeniorCitizen: e.target.value as 'Y' | 'N' | 'P' })}
            style={{ padding: '6px 10px', border: '1px solid #ddd', borderRadius: 4, fontSize: 12 }}>
            <option value="N">Non-Senior Citizen (cap ₹25,000)</option>
            <option value="Y">Senior Citizen (cap ₹50,000)</option>
            <option value="P">Not claiming for Parents</option>
          </select>
        </div>
      </div>

      {/* Category cards */}
      <CategoryCard title="Self & Family" color="#1565c0" catKey="selfFamily" cap={CAP_SELF_FAMILY} srFlag={data.selfSeniorCitizen} isVisible={showSelfFamily} />
      <CategoryCard title="Self & Family (Senior Citizen)" color="#2e7d32" catKey="selfFamilySenior" cap={CAP_SELF_FAMILY_SR} srFlag={data.selfSeniorCitizen} isVisible={showSelfFamilySr} />
      <CategoryCard title="Parents" color="#ef6c00" catKey="parents" cap={CAP_PARENTS} srFlag={data.parentsSeniorCitizen} isVisible={showParents} />
      <CategoryCard title="Parents (Senior Citizen)" color="#6a1b9a" catKey="parentsSenior" cap={CAP_PARENTS_SR} srFlag={data.parentsSeniorCitizen} isVisible={showParentsSr} />

      {/* Grand total */}
      <div style={{
        marginTop: 14, padding: 12, background: '#e8eaf6', borderRadius: 6,
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>Total 80D Eligible Deduction</span>
        <span style={{ fontWeight: 700, fontSize: 16, color: '#2e7d32' }}>₹{totalEligible.toLocaleString('en-IN')}</span>
      </div>
    </div>
  );
};

const inlineInputStyle: React.CSSProperties = {
  padding: '3px 6px', border: '1px solid #e0e0e0', borderRadius: 3,
  fontSize: 12, boxSizing: 'border-box', width: '100%',
};
