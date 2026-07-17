import React, { useState, useEffect } from 'react';
import { calculateHouseProperty, type HousePropertyInput, type PropertyCalculation, type HousePropertyCalculationResponse } from '../services/housePropertyCalculationService';

// Comprehensive House Property Entry interface - CBDT AY 2026-27 compliant
interface HousePropertyEntry {
  // ===== Property Identification =====
  id: string;
  name: string;  // User-friendly name for identification
  propertySequenceNo: number;  // HPSNo (1 or 2 for ITR-1)
  
  // ===== Property Type =====
  propertyType: 'SELF_OCCUPIED' | 'LET_OUT' | 'DEEMED_LET_OUT';
  
  // ===== Full Address =====
  address: string;           // AddrDetail
  premisesName?: string;    // ResidenceName (NEW)
  roadOrStreet?: string;    // RoadOrStreet (NEW)
  area?: string;           // LocalityOrArea (NEW)
  city: string;             // CityOrTownOrDistrict
  state: string;
  pinCode: string;
  countryCode?: string;     // Default "91" (NEW)
  propertyIdentificationNo: string;
  
  // ===== Ownership (NEW AY 2026-27) =====
  propertyOwnerType: 'SE' | 'MI' | 'SP' | 'OT';  // Single/Minor/Self+Spouse/Others
  ownershipType: 'SOLE' | 'JOINT';
  ownershipShare: number;   // Percentage
  isCoOwned: boolean;
  isPropertyInJointOwnership?: boolean;
  coOwners: Array<{
    coOwnerSNo?: number;
    name: string;
    pan: string;
    aadhaar?: string;     // NEW AY 2026-27
    share: number;
  }>;
  
  // ===== Let-out property fields =====
  annualRent: number;
  municipalRateableValue: number;
  fairRentValue: number;
  standardRent: number;
  annualLettingValue: number;
  unrealizedRent: number;
  arrearsOfRent: number;
  vacancyPeriodMonths: number;
  
  // ===== Deductions =====
  municipalTaxesPaid: number;
  interestOnLoan: number;
  preConstructionInterest: number;
  
  // ===== Loan Details - Section 24B (NEW AY 2026-27) =====
  lenderName: string;
  lenderPAN: string;
  lenderType?: 'B' | 'I' | 'L';  // Bank/Institution/Lender
  loanAccountNo: string;
  loanSanctionDate: string;
  constructionCompletionDate: string;
  principalRepayment: number;
  totalLoanAmount?: number;        // NEW
  loanOutstandingAmount?: number;   // NEW
  completedWithin5Years?: boolean;  // NEW
  
  // ===== Home Loans List (NEW AY 2026-27) =====
  homeLoans?: Array<{
    lenderType?: 'B' | 'I' | 'L';
    lenderName: string;
    lenderPAN?: string;
    loanAccountNo?: string;
    dateOfLoan?: string;
    totalLoanAmount?: number;
    loanOutstandingAmount?: number;
    interestUs24B?: number;
    constructionCompletionDate?: string;
    completedWithin5Years?: boolean;
    preConstructionInterest?: number;
  }>;
  
  // ===== Tenant Details (NEW AY 2026-27) =====
  tenantName: string;
  tenantPAN: string;
  tenantAadhaar?: string;  // NEW
  
  // ===== Computed (from Backend) =====
  grossAnnualValue: number;
  netAnnualValue: number;
  standardDeduction30Pct: number;
  incomeFromHP: number;  // CAN BE NEGATIVE (LOSS)
  
  // Max rent calculations
  maxRent?: number;
  
  // ===== Pre-construction interest =====
  preConstructionInterestClaimed?: number;
}

interface HousePropertyEntryManagerProps {
  entries: HousePropertyEntry[];
  onChange: (entries: HousePropertyEntry[]) => void;
  itrForm: string;
}

export function HousePropertyEntryManager({ entries, onChange, itrForm }: HousePropertyEntryManagerProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [showCoOwnerModal, setShowCoOwnerModal] = useState<number | null>(null);
  const [calculationResponse, setCalculationResponse] = useState<HousePropertyCalculationResponse | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);

  // Normalize ITR form (handle both 'ITR-1' and 'ITR1' formats)
  const normalizedForm = itrForm.replace('-', '');
  const maxProperties = normalizedForm === 'ITR1' ? 1 : 999;

  const recalculateAllProperties = async (updatedEntries: HousePropertyEntry[]) => {
    try {
      // Map frontend entry format to API input format
      const inputs: HousePropertyInput[] = updatedEntries.map(entry => ({
        propertySequenceNo: entry.propertySequenceNo || 1,
        propertyType: entry.propertyType,
        address: entry.address,
        city: entry.city,
        state: entry.state,
        pinCode: entry.pinCode,
        propertyIdentificationNo: entry.propertyIdentificationNo,
        propertyOwnerType: entry.propertyOwnerType,
        ownershipType: entry.ownershipType,
        ownershipShare: entry.ownershipShare,
        isCoOwned: entry.isCoOwned,
        coOwners: entry.coOwners?.map(co => ({
          name: co.name,
          pan: co.pan,
          aadhaar: co.aadhaar || '',
          sharePercentage: co.share
        })),
        annualRent: entry.annualRent,
        municipalRateableValue: entry.municipalRateableValue,
        fairRentValue: entry.fairRentValue,
        standardRent: entry.standardRent,
        unrealizedRent: entry.unrealizedRent,
        arrearsOfRent: entry.arrearsOfRent,
        vacancyPeriodMonths: entry.vacancyPeriodMonths,
        municipalTaxesPaid: entry.municipalTaxesPaid,
        interestOnLoan: entry.interestOnLoan,
        preConstructionInterest: entry.preConstructionInterest,
        homeLoans: entry.homeLoans?.map(loan => ({
          lenderType: loan.lenderType || 'B',
          lenderName: loan.lenderName || '',
          lenderPAN: loan.lenderPAN || '',
          loanAccountNo: loan.loanAccountNo || '',
          dateOfLoan: loan.dateOfLoan || '',
          totalLoanAmount: loan.totalLoanAmount || 0,
          loanOutstandingAmount: loan.loanOutstandingAmount || 0,
          interestUs24B: loan.interestUs24B || entry.interestOnLoan || 0
        })) || undefined,
        tenantName: entry.tenantName,
        tenantPAN: entry.tenantPAN,
        tenantAadhaar: entry.tenantAadhaar || ''
      }));

      const response = await calculateHouseProperty(itrForm.replace('-', '').replace('ITR', '2025-26'), inputs);
      setCalculationResponse(response);

      // Map response back to entries
      const recalculated = updatedEntries.map((entry, idx) => {
        const calc = response.properties[idx];
        if (!calc) return entry;
        return {
          ...entry,
          grossAnnualValue: calc.grossAnnualValue || 0,
          netAnnualValue: calc.netAnnualValue || 0,
          standardDeduction30Pct: calc.standardDeduction || 0,
          incomeFromHP: calc.incomeFromHP || 0,
        };
      });
      onChange(recalculated);
    } catch (error) {
      console.error('Error calculating house property:', error);
    }
  };

  // Auto-recalculate ONLY on initial load when entries have stale computed values
  // We do NOT depend on [entries] in the second useEffect to avoid infinite loops:
  // updateEntry -> onChange -> parent re-renders -> entries prop changes -> useEffect fires
  // -> recalculateAllProperties -> onChange again -> infinite loop
  useEffect(() => {
    if (!isInitialized && entries.length > 0) {
      // Check if needs recalculation (old format with computed values)
      const needsRecalculation = entries.some(e => e.grossAnnualValue === 0 && (e.annualRent > 0 || e.interestOnLoan > 0));
      if (needsRecalculation) {
        recalculateAllProperties(entries);
      }
      setIsInitialized(true);
    }
  }, [entries, isInitialized]);
  // NOTE: The second useEffect that called recalculateAllProperties on every [entries] change
  // has been intentionally removed to prevent the infinite loop:
  //   updateEntry -> onChange -> entries prop change -> useEffect -> recalculate -> onChange -> loop
  // Recalculation is now triggered directly inside updateEntry() after field changes.

  const addProperty = () => {
    if (entries.length >= maxProperties) {
      alert(`ITR-${itrForm.replace('ITR', '')} allows maximum ${maxProperties} property/properties`);
      return;
    }

    const newEntry: HousePropertyEntry = {
      id: `hp_${Date.now()}`,
      name: '',
      propertySequenceNo: entries.length + 1,
      propertyType: 'SELF_OCCUPIED',
      address: '',
      premisesName: '',
      roadOrStreet: '',
      area: '',
      city: '',
      state: '',
      pinCode: '',
      countryCode: '91',
      propertyIdentificationNo: '',
      propertyOwnerType: 'SE',
      ownershipType: 'SOLE',
      ownershipShare: 100,
      isCoOwned: false,
      isPropertyInJointOwnership: false,
      coOwners: [],
      annualRent: 0,
      municipalRateableValue: 0,
      fairRentValue: 0,
      standardRent: 0,
      annualLettingValue: 0,
      unrealizedRent: 0,
      arrearsOfRent: 0,
      vacancyPeriodMonths: 0,
      municipalTaxesPaid: 0,
      interestOnLoan: 0,
      preConstructionInterest: 0,
      lenderName: '',
      lenderPAN: '',
      lenderType: 'B',
      loanAccountNo: '',
      loanSanctionDate: '',
      constructionCompletionDate: '',
      principalRepayment: 0,
      totalLoanAmount: 0,
      loanOutstandingAmount: 0,
      completedWithin5Years: true,
      homeLoans: [],
      tenantName: '',
      tenantPAN: '',
      tenantAadhaar: '',
      grossAnnualValue: 0,
      netAnnualValue: 0,
      standardDeduction30Pct: 0,
      incomeFromHP: 0,
      maxRent: 0,
      preConstructionInterestClaimed: 0
    };

    onChange([...entries, newEntry]);
    setExpandedIndex(entries.length);
  };

  const updateEntry = (index: number, field: string, value: any) => {
    const updated = [...entries];
    updated[index] = { ...updated[index], [field]: value };
    onChange(updated);
    // Trigger backend recalculation
    if (isInitialized) {
      recalculateAllProperties(updated);
    }
  };

  const removeEntry = (index: number) => {
    const updated = entries.filter((_, i) => i !== index);
    onChange(updated);
    if (expandedIndex === index) setExpandedIndex(null);
  };

  const addCoOwner = (propertyIndex: number) => {
    const updated = [...entries];
    updated[propertyIndex].coOwners.push({ name: '', pan: '', share: 0 });
    onChange(updated);
  };

  const updateCoOwner = (propertyIndex: number, coOwnerIndex: number, field: string, value: any) => {
    const updated = [...entries];
    updated[propertyIndex].coOwners[coOwnerIndex] = {
      ...updated[propertyIndex].coOwners[coOwnerIndex],
      [field]: value
    };
    onChange(updated);
  };

  const removeCoOwner = (propertyIndex: number, coOwnerIndex: number) => {
    const updated = [...entries];
    updated[propertyIndex].coOwners = updated[propertyIndex].coOwners.filter((_, i) => i !== coOwnerIndex);
    onChange(updated);
  };

  const totalIncome = calculationResponse?.totalIncomeFromHP ?? entries.reduce((sum, e) => sum + e.incomeFromHP, 0);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)' }}>
          House Property Entries ({entries.length}/{maxProperties === 999 ? '∞' : maxProperties})
        </h3>
        <button
          onClick={addProperty}
          disabled={entries.length >= maxProperties}
          style={{
            padding: '6px 12px',
            background: entries.length >= maxProperties ? 'var(--border)' : 'var(--gold)',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            fontSize: 13,
            cursor: entries.length >= maxProperties ? 'not-allowed' : 'pointer'
          }}
        >
          + Add Property
        </button>
      </div>

      {entries.length === 0 && (
        <div style={{ padding: 24, textAlign: 'center', background: 'var(--bg)', borderRadius: 6, border: '1px dashed var(--border)' }}>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 12 }}>
            No house property entries added yet
          </p>
          <button
            onClick={addProperty}
            style={{
              padding: '8px 16px',
              background: 'var(--gold)',
              color: 'white',
              border: 'none',
              borderRadius: 6,
              fontSize: 13,
              cursor: 'pointer'
            }}
          >
            Add First Property
          </button>
        </div>
      )}

      {entries.map((entry, index) => (
        <div
          key={entry.id}
          style={{
            marginBottom: 12,
            border: '1px solid var(--border)',
            borderRadius: 6,
            overflow: 'hidden'
          }}
        >
          {/* Header */}
          <div
            onClick={() => setExpandedIndex(expandedIndex === index ? null : index)}
            style={{
              padding: 12,
              background: 'var(--bg)',
              cursor: 'pointer',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 13, fontWeight: 600 }}>
                {entry.name ? entry.name : `Property #${index + 1}`}
              </span>
              <span style={{
                padding: '2px 8px',
                background: entry.propertyType === 'SELF_OCCUPIED' ? 'var(--info-bg)' : 'var(--success-bg)',
                color: entry.propertyType === 'SELF_OCCUPIED' ? 'var(--info)' : 'var(--success)',
                borderRadius: 4,
                fontSize: 11,
                fontWeight: 500
              }}>
                {entry.propertyType.replace('_', ' ')}
              </span>
              {entry.address && (
                <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                  {entry.address.substring(0, 40)}{entry.address.length > 40 ? '...' : ''}
                </span>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 13, fontFamily: 'DM Mono', color: entry.incomeFromHP >= 0 ? 'var(--success)' : 'var(--error)' }}>
                ₹{entry.incomeFromHP.toLocaleString('en-IN')}
              </span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  removeEntry(index);
                }}
                style={{
                  padding: '4px 8px',
                  background: 'var(--error-bg)',
                  color: 'var(--error)',
                  border: 'none',
                  borderRadius: 4,
                  fontSize: 11,
                  cursor: 'pointer'
                }}
              >
                Remove
              </button>
              <span style={{ fontSize: 18, color: 'var(--text-secondary)' }}>
                {expandedIndex === index ? '▼' : '▶'}
              </span>
            </div>
          </div>

          {/* Expanded Content */}
          {expandedIndex === index && (
            <div style={{ padding: 16, background: 'white' }}>
              {/* Property Details */}
              <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: 'var(--text-secondary)' }}>
                Property Details (CBDT Mandatory)
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 16 }}>
                <div>
                  <label style={{ display: 'block', marginBottom: 4, fontSize: 11, fontWeight: 500 }}>Property Name (for easy identification)</label>
                  <input
                    type="text"
                    value={entry.name || ''}
                    onChange={(e) => updateEntry(index, 'name', e.target.value)}
                    placeholder="e.g., Mumbai Flat, Bangalore Villa"
                    style={{ width: '100%', padding: '6px 8px', border: '1px solid var(--border)', borderRadius: 4, fontSize: 12 }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: 4, fontSize: 11, fontWeight: 500 }}>Property Type *</label>
                  <select
                    value={entry.propertyType}
                    onChange={(e) => updateEntry(index, 'propertyType', e.target.value)}
                    style={{ width: '100%', padding: '6px 8px', border: '1px solid var(--border)', borderRadius: 4, fontSize: 12 }}
                  >
                    <option value="SELF_OCCUPIED">Self Occupied</option>
                    <option value="LET_OUT">Let Out</option>
                    <option value="DEEMED_LET_OUT">Deemed Let Out</option>
                  </select>
                </div>
                <InputField label="Property ID/Survey No *" value={entry.propertyIdentificationNo} onChange={(v) => updateEntry(index, 'propertyIdentificationNo', v)} type="text" />
                <div>
                  <label style={{ display: 'block', marginBottom: 4, fontSize: 11, fontWeight: 500 }}>Ownership Type *</label>
                  <select
                    value={entry.ownershipType}
                    onChange={(e) => updateEntry(index, 'ownershipType', e.target.value)}
                    style={{ width: '100%', padding: '6px 8px', border: '1px solid var(--border)', borderRadius: 4, fontSize: 12 }}
                  >
                    <option value="SOLE">Sole Ownership</option>
                    <option value="JOINT">Joint Ownership</option>
                  </select>
                </div>
                <InputField label="Address *" value={entry.address} onChange={(v) => updateEntry(index, 'address', v)} type="text" />
                <InputField label="City *" value={entry.city} onChange={(v) => updateEntry(index, 'city', v)} type="text" />
                <InputField label="State *" value={entry.state} onChange={(v) => updateEntry(index, 'state', v)} type="text" />
                <InputField label="PIN Code *" value={entry.pinCode} onChange={(v) => updateEntry(index, 'pinCode', v)} type="text" />
                <InputField label="Your Ownership Share %" value={entry.ownershipShare} onChange={(v) => updateEntry(index, 'ownershipShare', v)} />
                <div>
                  <label style={{ display: 'block', marginBottom: 4, fontSize: 11, fontWeight: 500 }}>Is Property Co-owned?</label>
                  <select
                    value={entry.isCoOwned ? 'YES' : 'NO'}
                    onChange={(e) => updateEntry(index, 'isCoOwned', e.target.value === 'YES')}
                    style={{ width: '100%', padding: '6px 8px', border: '1px solid var(--border)', borderRadius: 4, fontSize: 12 }}
                  >
                    <option value="NO">No</option>
                    <option value="YES">Yes</option>
                  </select>
                </div>
              </div>

              {/* Co-owners Section */}
              {entry.isCoOwned && (
                <div style={{ marginTop: 16, padding: 12, background: 'var(--bg)', borderRadius: 6 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <h5 style={{ fontSize: 12, fontWeight: 600 }}>Co-owners Details</h5>
                    <button
                      onClick={() => addCoOwner(index)}
                      style={{
                        padding: '4px 8px',
                        background: 'var(--gold)',
                        color: 'white',
                        border: 'none',
                        borderRadius: 4,
                        fontSize: 11,
                        cursor: 'pointer'
                      }}
                    >
                      + Add Co-owner
                    </button>
                  </div>
                  {entry.coOwners.map((coOwner, coIndex) => (
                    <div key={coIndex} style={{ display: 'grid', gridTemplateColumns: '2fr 2fr 1fr auto', gap: 8, marginBottom: 8, alignItems: 'end' }}>
                      <InputField label="Co-owner Name" value={coOwner.name} onChange={(v) => updateCoOwner(index, coIndex, 'name', v)} type="text" />
                      <InputField label="Co-owner PAN" value={coOwner.pan} onChange={(v) => updateCoOwner(index, coIndex, 'pan', v)} type="text" />
                      <InputField label="Share %" value={coOwner.share} onChange={(v) => updateCoOwner(index, coIndex, 'share', v)} />
                      <button
                        onClick={() => removeCoOwner(index, coIndex)}
                        style={{
                          padding: '6px 8px',
                          background: 'var(--error-bg)',
                          color: 'var(--error)',
                          border: 'none',
                          borderRadius: 4,
                          fontSize: 11,
                          cursor: 'pointer'
                        }}
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* Let-out Property Fields */}
              {entry.propertyType === 'LET_OUT' && (
                <>
                  <h4 style={{ fontSize: 13, fontWeight: 600, marginTop: 16, marginBottom: 12, color: 'var(--text-secondary)' }}>
                    Rental Income Details (CBDT Schedule HP)
                  </h4>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 16 }}>
                    <InputField label="Annual Rent Received" value={entry.annualRent} onChange={(v) => updateEntry(index, 'annualRent', v)} />
                    <InputField label="Municipal Rateable Value" value={entry.municipalRateableValue} onChange={(v) => updateEntry(index, 'municipalRateableValue', v)} />
                    <InputField label="Fair Rent Value" value={entry.fairRentValue} onChange={(v) => updateEntry(index, 'fairRentValue', v)} />
                    <InputField label="Standard Rent (if applicable)" value={entry.standardRent} onChange={(v) => updateEntry(index, 'standardRent', v)} />
                    <InputField label="Unrealized Rent" value={entry.unrealizedRent} onChange={(v) => updateEntry(index, 'unrealizedRent', v)} />
                    <InputField label="Arrears of Rent Received" value={entry.arrearsOfRent} onChange={(v) => updateEntry(index, 'arrearsOfRent', v)} />
                    <InputField label="Vacancy Period (months)" value={entry.vacancyPeriodMonths} onChange={(v) => updateEntry(index, 'vacancyPeriodMonths', v)} />
                    <InputField label="Municipal Taxes Paid" value={entry.municipalTaxesPaid} onChange={(v) => updateEntry(index, 'municipalTaxesPaid', v)} />
                  </div>

                  {/* Detailed HP computation breakdown - matches salary tab style */}
                  <div style={{ padding: '14px 16px', background: '#fef3e2', borderRadius: 8, marginBottom: 16, border: '1px solid #f3d9a8' }}>
                    {/* Gross Annual Value */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: 8, borderBottom: '1px dashed #f3d9a8' }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: '#1e293b' }}>Gross Annual Value (GAV)</span>
                      <span style={{ fontSize: 14, fontWeight: 700, color: '#1e293b' }}>₹{entry.grossAnnualValue.toLocaleString('en-IN')}</span>
                    </div>

                    {/* Municipal Taxes */}
                    <div style={{ paddingTop: 8, paddingBottom: 8, borderBottom: '1px dashed #f3d9a8' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#64748b' }}>
                        <span>Less: Municipal Taxes Paid</span>
                        <span style={{ color: '#ef4444' }}>- ₹{entry.municipalTaxesPaid.toLocaleString('en-IN')}</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, fontWeight: 600, color: '#1e293b', marginTop: 6 }}>
                        <span>= Net Annual Value (NAV)</span>
                        <span>₹{entry.netAnnualValue.toLocaleString('en-IN')}</span>
                      </div>
                    </div>

                    {/* Standard Deduction 30% */}
                    <div style={{ paddingTop: 8, paddingBottom: 8, borderBottom: '1px dashed #f3d9a8' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#64748b' }}>
                        <span>Less: Standard Deduction u/s 24(a) <span style={{ fontSize: 10, color: '#94a3b8' }}>(30% of NAV)</span></span>
                        <span style={{ color: '#ef4444' }}>- ₹{entry.standardDeduction30Pct.toLocaleString('en-IN')}</span>
                      </div>
                    </div>

                    {/* Interest on Loan */}
                    <div style={{ paddingTop: 8, paddingBottom: 8, borderBottom: '1px dashed #f3d9a8' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#64748b' }}>
                        <span>
                          Less: Interest on Loan u/s 24(b)
                          {entry.interestOnLoan > 0 && (
                            <span style={{ fontSize: 10, color: '#94a3b8', marginLeft: 4 }}>(uncapped for let-out)</span>
                          )}
                        </span>
                        <span style={{ color: '#ef4444' }}>
                          - ₹{((entry.interestOnLoan || 0) + (entry.preConstructionInterest > 0 ? entry.preConstructionInterest / 5 : 0)).toLocaleString('en-IN')}
                        </span>
                      </div>
                      {entry.preConstructionInterest > 0 && (
                        <div style={{ fontSize: 11, color: '#94a3b8', paddingLeft: 8, marginTop: 2 }}>
                          Includes pre-construction interest: ₹{(entry.preConstructionInterest / 5).toLocaleString('en-IN')} (1/5th of ₹{entry.preConstructionInterest.toLocaleString('en-IN')})
                        </div>
                      )}
                    </div>

                    {/* Net Income from HP */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 10 }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: '#1e293b' }}>= Income from House Property</span>
                      <span style={{ fontSize: 16, fontWeight: 700, color: entry.incomeFromHP >= 0 ? '#16a34a' : '#dc2626' }}>
                        ₹{entry.incomeFromHP.toLocaleString('en-IN')}
                      </span>
                    </div>
                  </div>

                  <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: 'var(--text-secondary)' }}>
                    Tenant Details
                  </h4>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 16 }}>
                    <InputField label="Tenant Name" value={entry.tenantName} onChange={(v) => updateEntry(index, 'tenantName', v)} type="text" />
                    <InputField label="Tenant PAN" value={entry.tenantPAN} onChange={(v) => updateEntry(index, 'tenantPAN', v)} type="text" />
                  </div>
                </>
              )}

              {/* Loan Details */}
              <h4 style={{ fontSize: 13, fontWeight: 600, marginTop: 16, marginBottom: 12, color: 'var(--text-secondary)' }}>
                Home Loan Details (if applicable)
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 16 }}>
                <InputField label="Interest on Loan" value={entry.interestOnLoan} onChange={(v) => updateEntry(index, 'interestOnLoan', v)} />
                <InputField label="Pre-construction Interest" value={entry.preConstructionInterest} onChange={(v) => updateEntry(index, 'preConstructionInterest', v)} />
                <InputField label="Principal Repayment (for 80C)" value={entry.principalRepayment} onChange={(v) => updateEntry(index, 'principalRepayment', v)} />
                <InputField label="Lender Name" value={entry.lenderName} onChange={(v) => updateEntry(index, 'lenderName', v)} type="text" />
                <InputField label="Lender PAN" value={entry.lenderPAN} onChange={(v) => updateEntry(index, 'lenderPAN', v)} type="text" />
                <InputField label="Loan Account Number" value={entry.loanAccountNo} onChange={(v) => updateEntry(index, 'loanAccountNo', v)} type="text" />
                <InputField label="Loan Sanction Date" value={entry.loanSanctionDate} onChange={(v) => updateEntry(index, 'loanSanctionDate', v)} type="date" />
                <InputField label="Construction Completion Date" value={entry.constructionCompletionDate} onChange={(v) => updateEntry(index, 'constructionCompletionDate', v)} type="date" />
              </div>

              {/* Income Summary */}
              <div style={{ marginTop: 16, padding: 12, background: entry.incomeFromHP >= 0 ? 'var(--success-bg)' : 'var(--error-bg)', borderRadius: 6 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: entry.incomeFromHP >= 0 ? 'var(--success)' : 'var(--error)' }}>
                  Income/Loss from this Property: ₹{entry.incomeFromHP.toLocaleString('en-IN')}
                </div>
              </div>
            </div>
          )}
        </div>
      ))}

      {/* Total Summary */}
      {entries.length > 0 && (
        <div style={{ marginTop: 16, padding: 16, background: 'var(--gold-pale)', borderRadius: 6, border: '1px solid var(--gold)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 14, fontWeight: 600 }}>Total Income from House Property</span>
            <span style={{ fontSize: 16, fontWeight: 600, fontFamily: 'DM Mono', color: totalIncome >= 0 ? 'var(--success)' : 'var(--error)' }}>
              ₹{totalIncome.toLocaleString('en-IN')}
            </span>
          </div>
        </div>
      )}

      {/* CBDT Compliance Info */}
      <div style={{ marginTop: 16, padding: 12, background: 'var(--info-bg)', borderRadius: 6, fontSize: 11, color: 'var(--info)' }}>
        <strong>CBDT Schedule HP Requirements:</strong>
        <ul style={{ marginTop: 8, paddingLeft: 20, marginBottom: 0 }}>
          <li>Property Identification Number (Survey/Plot No) is mandatory</li>
          <li>For let-out property: GAV = Higher of (Rent, Municipal Value, Fair Rent) - Unrealized Rent</li>
          <li>Standard Deduction: 30% of Net Annual Value (automatic)</li>
          <li>Self-occupied: Interest deduction limited to ₹2,00,000</li>
          <li>Pre-construction interest: Deductible in 5 equal installments</li>
          <li>Co-owner details required if property is jointly owned</li>
        </ul>
      </div>
    </div>
  );
}

// Helper Input Field Component
interface InputFieldProps {
  label: string;
  value: string | number;
  onChange: (value: string | number) => void;
  type?: 'text' | 'number' | 'date';
}

function InputField({ label, value, onChange, type = 'number' }: InputFieldProps) {
  return (
    <div>
      <label style={{ display: 'block', marginBottom: 4, fontSize: 11, fontWeight: 500, color: 'var(--text-secondary)' }}>
        {label}
      </label>
      <input
        type={type}
        value={value || (type === 'number' ? 0 : '')}
        onChange={(e) => onChange(type === 'number' ? Number(e.target.value) : e.target.value)}
        style={{
          width: '100%',
          padding: '6px 8px',
          border: '1px solid var(--border)',
          borderRadius: 4,
          fontSize: 12,
          fontFamily: type === 'number' ? 'DM Mono' : 'inherit'
        }}
      />
    </div>
  );
}
