import { useState } from 'react';
import { advancedTaxApi } from '../api/advancedTax';
import toast from 'react-hot-toast';
import { IndianNumberInput } from '../components/IndianNumberInput';

export default function AdvancedTaxPage() {
  const [activeCalculator, setActiveCalculator] = useState<string>('hra');
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const calculators = [
    { id: 'hra', name: 'HRA Exemption', icon: '🏠' },
    { id: 'section14a', name: 'Section 14A', icon: '📊' },
    { id: 'section50c', name: 'Section 50C', icon: '🏘️' },
    { id: 'relief89', name: 'Relief u/s 89', icon: '💰' },
    { id: 'depreciation', name: 'Depreciation', icon: '📉' },
    { id: 'multiEmployer', name: 'Multi-Employer', icon: '👥' },
    { id: 'ltcg', name: 'LTCG Grandfathering', icon: '📈' },
    { id: 'epf', name: 'EPF Taxation', icon: '🏦' },
    { id: 'clubbing', name: 'Clubbing', icon: '👨‍👩‍👧' },
    { id: 'foTrading', name: 'F&O Trading', icon: '📊' },
    { id: 'breakEven', name: 'Break-Even', icon: '⚖️' },
  ];

  const renderCalculator = () => {
    switch (activeCalculator) {
      case 'hra':
        return <HRACalculator onResult={setResult} setLoading={setLoading} />;
      case 'section14a':
        return <Section14ACalculator onResult={setResult} setLoading={setLoading} />;
      case 'section50c':
        return <Section50CCalculator onResult={setResult} setLoading={setLoading} />;
      case 'relief89':
        return <Relief89Calculator onResult={setResult} setLoading={setLoading} />;
      case 'depreciation':
        return <DepreciationCalculator onResult={setResult} setLoading={setLoading} />;
      case 'multiEmployer':
        return <MultiEmployerCalculator onResult={setResult} setLoading={setLoading} />;
      case 'ltcg':
        return <LTCGCalculator onResult={setResult} setLoading={setLoading} />;
      case 'epf':
        return <EPFCalculator onResult={setResult} setLoading={setLoading} />;
      case 'clubbing':
        return <ClubbingCalculator onResult={setResult} setLoading={setLoading} />;
      case 'foTrading':
        return <FOTradingCalculator onResult={setResult} setLoading={setLoading} />;
      case 'breakEven':
        return <BreakEvenCalculator onResult={setResult} setLoading={setLoading} />;
      default:
        return null;
    }
  };

  return (
    <div>
      <h1 className="crimson" style={{ fontSize: 22, marginBottom: 24 }}>Advanced Tax Calculators</h1>

      <div style={{ display: 'grid', gridTemplateColumns: '250px 1fr', gap: 24 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {calculators.map((calc) => (
            <button
              key={calc.id}
              onClick={() => {
                setActiveCalculator(calc.id);
                setResult(null);
              }}
              style={{
                padding: '12px 16px',
                background: activeCalculator === calc.id ? 'var(--gold)' : 'white',
                color: activeCalculator === calc.id ? 'white' : 'var(--text-primary)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                fontSize: 13,
                fontWeight: 500,
                cursor: 'pointer',
                textAlign: 'left',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <span>{calc.icon}</span>
              <span>{calc.name}</span>
            </button>
          ))}
        </div>

        <div style={{ background: 'white', padding: 24, borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
          {renderCalculator()}
          
          {loading && (
            <div style={{ textAlign: 'center', padding: 24 }}>
              <div className="spinner" />
            </div>
          )}

          {result && !loading && (
            <div style={{ marginTop: 24, padding: 16, background: 'var(--bg)', borderRadius: 6 }}>
              <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Result</h3>
              <pre style={{ fontSize: 12, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {JSON.stringify(result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function HRACalculator({ onResult, setLoading }: any) {
  const [formData, setFormData] = useState({
    hraReceived: 0,
    basicDA: 0,
    rentPaid: 0,
    cityType: 'METRO' as 'METRO' | 'NON_METRO',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const result = await advancedTaxApi.computeHRA(formData);
      onResult(result);
      toast.success('HRA exemption calculated');
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>HRA Exemption Calculator</h3>
      
      <div style={{ display: 'grid', gap: 16 }}>
        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            HRA Received
          </label>
          <IndianNumberInput
            value={formData.hraReceived}
            onChange={(v) => setFormData({ ...formData, hraReceived: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Basic + DA
          </label>
          <IndianNumberInput
            value={formData.basicDA}
            onChange={(v) => setFormData({ ...formData, basicDA: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Rent Paid
          </label>
          <IndianNumberInput
            value={formData.rentPaid}
            onChange={(v) => setFormData({ ...formData, rentPaid: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            City Type
          </label>
          <select
            value={formData.cityType}
            onChange={(e) => setFormData({ ...formData, cityType: e.target.value as any })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          >
            <option value="METRO">Metro</option>
            <option value="NON_METRO">Non-Metro</option>
          </select>
        </div>

        <button
          type="submit"
          style={{
            padding: '10px 16px',
            background: 'var(--gold)',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Calculate HRA Exemption
        </button>
      </div>
    </form>
  );
}

function Section14ACalculator({ onResult, setLoading }: any) {
  const [formData, setFormData] = useState({
    directExpensesRelatedToExemptIncome: 0,
    exemptIncome: 0,
    avgInvestmentInExemptIncome: 0,
    totalInterestExpense: 0,
    avgTotalAssets: 0,
    totalExpenses: 0,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const result = await advancedTaxApi.computeSection14A(formData);
      onResult(result);
      toast.success('Section 14A disallowance calculated');
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Section 14A Disallowance</h3>
      
      <div style={{ display: 'grid', gap: 16 }}>
        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Direct Expenses Related to Exempt Income
          </label>
          <IndianNumberInput
            value={formData.directExpensesRelatedToExemptIncome}
            onChange={(v) => setFormData({ ...formData, directExpensesRelatedToExemptIncome: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Exempt Income
          </label>
          <IndianNumberInput
            value={formData.exemptIncome}
            onChange={(v) => setFormData({ ...formData, exemptIncome: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Avg Investment in Exempt Income
          </label>
          <IndianNumberInput
            value={formData.avgInvestmentInExemptIncome}
            onChange={(v) => setFormData({ ...formData, avgInvestmentInExemptIncome: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Total Interest Expense
          </label>
          <IndianNumberInput
            value={formData.totalInterestExpense}
            onChange={(v) => setFormData({ ...formData, totalInterestExpense: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Avg Total Assets
          </label>
          <IndianNumberInput
            value={formData.avgTotalAssets}
            onChange={(v) => setFormData({ ...formData, avgTotalAssets: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Total Expenses
          </label>
          <IndianNumberInput
            value={formData.totalExpenses}
            onChange={(v) => setFormData({ ...formData, totalExpenses: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <button
          type="submit"
          style={{
            padding: '10px 16px',
            background: 'var(--gold)',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Calculate Disallowance
        </button>
      </div>
    </form>
  );
}

function Section50CCalculator({ onResult, setLoading }: any) {
  const [formData, setFormData] = useState({
    salePrice: 0,
    stampDutyValue: 0,
    isSellerTransaction: true,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const result = await advancedTaxApi.validateSection50C(formData);
      onResult(result);
      toast.success('Section 50C validation completed');
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Section 50C Property Validator</h3>
      
      <div style={{ display: 'grid', gap: 16 }}>
        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Sale/Purchase Price
          </label>
          <IndianNumberInput
            value={formData.salePrice}
            onChange={(v) => setFormData({ ...formData, salePrice: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Stamp Duty Value
          </label>
          <IndianNumberInput
            value={formData.stampDutyValue}
            onChange={(v) => setFormData({ ...formData, stampDutyValue: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
            <input
              type="checkbox"
              checked={formData.isSellerTransaction}
              onChange={(e) => setFormData({ ...formData, isSellerTransaction: e.target.checked })}
            />
            Seller Transaction (uncheck for buyer)
          </label>
        </div>

        <button
          type="submit"
          style={{
            padding: '10px 16px',
            background: 'var(--gold)',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Validate Section 50C
        </button>
      </div>
    </form>
  );
}

function Relief89Calculator({ onResult, setLoading }: any) {
  const [formData, setFormData] = useState({
    taxOnTotalIncomeWithArrears: 0,
    taxOnTotalIncomeWithoutArrears: 0,
    arrearEntries: [
      {
        yearToWhichArrearRelates: '2023-24',
        arrearAmount: 0,
        taxOnIncomeWithArrear: 0,
        taxOnIncomeWithoutArrear: 0,
      },
    ],
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const result = await advancedTaxApi.computeRelief89(formData);
      onResult(result);
      toast.success('Relief u/s 89 calculated');
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Relief u/s 89 - Salary Arrears</h3>
      
      <div style={{ display: 'grid', gap: 16 }}>
        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Tax on Total Income (With Arrears)
          </label>
          <IndianNumberInput
            value={formData.taxOnTotalIncomeWithArrears}
            onChange={(v) => setFormData({ ...formData, taxOnTotalIncomeWithArrears: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Tax on Total Income (Without Arrears)
          </label>
          <IndianNumberInput
            value={formData.taxOnTotalIncomeWithoutArrears}
            onChange={(v) => setFormData({ ...formData, taxOnTotalIncomeWithoutArrears: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div style={{ padding: 12, background: 'var(--bg)', borderRadius: 6 }}>
          <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Arrear Entry</h4>
          <div style={{ display: 'grid', gap: 12 }}>
            <input
              type="text"
              placeholder="Year (e.g., 2023-24)"
              value={formData.arrearEntries[0].yearToWhichArrearRelates}
              onChange={(e) => setFormData({
                ...formData,
                arrearEntries: [{ ...formData.arrearEntries[0], yearToWhichArrearRelates: e.target.value }]
              })}
              style={{ padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13 }}
            />
            <IndianNumberInput
              value={formData.arrearEntries[0].arrearAmount}
              onChange={(v) => setFormData({
                ...formData,
                arrearEntries: [{ ...formData.arrearEntries[0], arrearAmount: v }]
              })}
              placeholder="Arrear Amount"
              style={{ padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13 }}
            />
            <IndianNumberInput
              value={formData.arrearEntries[0].taxOnIncomeWithArrear}
              onChange={(v) => setFormData({
                ...formData,
                arrearEntries: [{ ...formData.arrearEntries[0], taxOnIncomeWithArrear: v }]
              })}
              placeholder="Tax With Arrear (That Year)"
              style={{ padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13 }}
            />
            <IndianNumberInput
              value={formData.arrearEntries[0].taxOnIncomeWithoutArrear}
              onChange={(v) => setFormData({
                ...formData,
                arrearEntries: [{ ...formData.arrearEntries[0], taxOnIncomeWithoutArrear: v }]
              })}
              placeholder="Tax Without Arrear (That Year)"
              style={{ padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13 }}
            />
          </div>
        </div>

        <button
          type="submit"
          style={{
            padding: '10px 16px',
            background: 'var(--gold)',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Calculate Relief
        </button>
      </div>
    </form>
  );
}

function DepreciationCalculator({ onResult, setLoading }: any) {
  const [formData, setFormData] = useState({
    openingWDV: 0,
    additionsFirstHalf: 0,
    additionsSecondHalf: 0,
    sales: 0,
    assetCategory: 'PLANT_MACHINERY_GENERAL',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const result = await advancedTaxApi.computeDepreciation(formData);
      onResult(result);
      toast.success('Depreciation calculated');
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Depreciation Calculator</h3>
      
      <div style={{ display: 'grid', gap: 16 }}>
        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Opening WDV
          </label>
          <IndianNumberInput
            value={formData.openingWDV}
            onChange={(v) => setFormData({ ...formData, openingWDV: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Additions (Before Oct 1)
          </label>
          <IndianNumberInput
            value={formData.additionsFirstHalf}
            onChange={(v) => setFormData({ ...formData, additionsFirstHalf: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Additions (After Oct 1)
          </label>
          <IndianNumberInput
            value={formData.additionsSecondHalf}
            onChange={(v) => setFormData({ ...formData, additionsSecondHalf: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Sales/Disposals
          </label>
          <IndianNumberInput
            value={formData.sales}
            onChange={(v) => setFormData({ ...formData, sales: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Asset Category
          </label>
          <select
            value={formData.assetCategory}
            onChange={(e) => setFormData({ ...formData, assetCategory: e.target.value })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          >
            <option value="BUILDING_RCC_RESIDENTIAL">Building RCC Residential (5%)</option>
            <option value="BUILDING_RCC_NON_RESIDENTIAL">Building RCC Non-Residential (10%)</option>
            <option value="FURNITURE_FITTINGS">Furniture & Fittings (10%)</option>
            <option value="PLANT_MACHINERY_GENERAL">Plant & Machinery (15%)</option>
            <option value="COMPUTERS_PERIPHERALS">Computers (40%)</option>
            <option value="MOTOR_CAR_GENERAL">Motor Car (15%)</option>
            <option value="MOTOR_BUS_LORRY_HIRE">Bus/Lorry (30%)</option>
          </select>
        </div>

        <button
          type="submit"
          style={{
            padding: '10px 16px',
            background: 'var(--gold)',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Calculate Depreciation
        </button>
      </div>
    </form>
  );
}

function MultiEmployerCalculator({ onResult, setLoading }: any) {
  const [employers, setEmployers] = useState([
    {
      employerName: '',
      employerTAN: '',
      employerPAN: '',
      grossSalary: 0,
      exemptAllowances: 0,
      // Standard deduction is computed by the backend based on the selected
      // tax regime (₹50K old / ₹75K new). Do NOT pre-fill a statutory default
      // here; the backend engine owns this value.
      standardDeduction: 0,
      professionalTax: 0,
      tdsDeducted: 0,
      periodFrom: '',
      periodTo: '',
    },
  ]);

  const addEmployer = () => {
    setEmployers([...employers, {
      employerName: '',
      employerTAN: '',
      employerPAN: '',
      grossSalary: 0,
      exemptAllowances: 0,
      // Standard deduction is computed by the backend based on the selected
      // tax regime (₹50K old / ₹75K new). Do NOT pre-fill a statutory default
      // here; the backend engine owns this value.
      standardDeduction: 0,
      professionalTax: 0,
      tdsDeducted: 0,
      periodFrom: '',
      periodTo: '',
    }]);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const result = await advancedTaxApi.consolidateMultiEmployer(employers);
      onResult(result);
      toast.success('Multi-employer consolidation completed');
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Multi-Employer Consolidation</h3>
      
      <div style={{ display: 'grid', gap: 16 }}>
        {employers.map((emp, idx) => (
          <div key={idx} style={{ padding: 12, background: 'var(--bg)', borderRadius: 6 }}>
            <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Employer {idx + 1}</h4>
            <div style={{ display: 'grid', gap: 12 }}>
              <input
                type="text"
                placeholder="Employer Name"
                value={emp.employerName}
                onChange={(e) => {
                  const newEmployers = [...employers];
                  newEmployers[idx].employerName = e.target.value;
                  setEmployers(newEmployers);
                }}
                style={{ padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13 }}
              />
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <IndianNumberInput
                  value={emp.grossSalary}
                  onChange={(v) => {
                    const newEmployers = [...employers];
                    newEmployers[idx].grossSalary = v;
                    setEmployers(newEmployers);
                  }}
                  placeholder="Gross Salary"
                  style={{ padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13 }}
                />
                <IndianNumberInput
                  value={emp.tdsDeducted}
                  onChange={(v) => {
                    const newEmployers = [...employers];
                    newEmployers[idx].tdsDeducted = v;
                    setEmployers(newEmployers);
                  }}
                  placeholder="TDS Deducted"
                  style={{ padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13 }}
                />
              </div>
            </div>
          </div>
        ))}

        <button
          type="button"
          onClick={addEmployer}
          style={{
            padding: '8px 16px',
            background: 'var(--border)',
            color: 'var(--text-primary)',
            border: 'none',
            borderRadius: 6,
            fontSize: 13,
            fontWeight: 500,
            cursor: 'pointer',
          }}
        >
          + Add Employer
        </button>

        <button
          type="submit"
          style={{
            padding: '10px 16px',
            background: 'var(--gold)',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Consolidate
        </button>
      </div>
    </form>
  );
}

function LTCGCalculator({ onResult, setLoading }: any) {
  const [formData, setFormData] = useState({
    acquisitionDate: '',
    saleDate: '',
    actualCost: 0,
    fmvJan312018: 0,
    saleValue: 0,
    transferExpenses: 0,
    isin: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const result = await advancedTaxApi.computeLTCGGrandfathering(formData);
      onResult(result);
      toast.success('LTCG grandfathering calculated');
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>LTCG Grandfathering (Jan 31, 2018)</h3>
      
      <div style={{ display: 'grid', gap: 16 }}>
        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Acquisition Date
          </label>
          <input
            type="date"
            value={formData.acquisitionDate}
            onChange={(e) => setFormData({ ...formData, acquisitionDate: e.target.value })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Sale Date
          </label>
          <input
            type="date"
            value={formData.saleDate}
            onChange={(e) => setFormData({ ...formData, saleDate: e.target.value })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Actual Cost
          </label>
          <IndianNumberInput
            value={formData.actualCost}
            onChange={(v) => setFormData({ ...formData, actualCost: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            FMV as on Jan 31, 2018
          </label>
          <IndianNumberInput
            value={formData.fmvJan312018}
            onChange={(v) => setFormData({ ...formData, fmvJan312018: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Sale Value
          </label>
          <IndianNumberInput
            value={formData.saleValue}
            onChange={(v) => setFormData({ ...formData, saleValue: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Transfer Expenses
          </label>
          <IndianNumberInput
            value={formData.transferExpenses}
            onChange={(v) => setFormData({ ...formData, transferExpenses: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <button
          type="submit"
          style={{
            padding: '10px 16px',
            background: 'var(--gold)',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Calculate LTCG
        </button>
      </div>
    </form>
  );
}

function EPFCalculator({ onResult, setLoading }: any) {
  const [formData, setFormData] = useState({
    employeeEPFContribution: 0,
    employeeVPFContribution: 0,
    totalInterestEarned: 0,
    employerHasPF: true,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const result = await advancedTaxApi.computeEPFTaxation(formData);
      onResult(result);
      toast.success('EPF taxation calculated');
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>EPF/VPF Taxation</h3>
      
      <div style={{ display: 'grid', gap: 16 }}>
        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Employee EPF Contribution
          </label>
          <IndianNumberInput
            value={formData.employeeEPFContribution}
            onChange={(v) => setFormData({ ...formData, employeeEPFContribution: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Employee VPF Contribution
          </label>
          <IndianNumberInput
            value={formData.employeeVPFContribution}
            onChange={(v) => setFormData({ ...formData, employeeVPFContribution: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Total Interest Earned
          </label>
          <IndianNumberInput
            value={formData.totalInterestEarned}
            onChange={(v) => setFormData({ ...formData, totalInterestEarned: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
            <input
              type="checkbox"
              checked={formData.employerHasPF}
              onChange={(e) => setFormData({ ...formData, employerHasPF: e.target.checked })}
            />
            Employer has PF (limit ₹2.5L, else ₹5L)
          </label>
        </div>

        <button
          type="submit"
          style={{
            padding: '10px 16px',
            background: 'var(--gold)',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Calculate EPF Tax
        </button>
      </div>
    </form>
  );
}

function ClubbingCalculator({ onResult, setLoading }: any) {
  const [clubbingType, setClubbingType] = useState<'minorChild' | 'spouse'>('minorChild');
  const [minorChildData, setMinorChildData] = useState({
    childIncome: 0,
    numberOfMinorChildren: 1,
    parent1Income: 0,
    parent2Income: 0,
  });
  const [spouseData, setSpouseData] = useState({
    spouseIncome: 0,
    transferType: 'Asset Transfer',
    adequateConsideration: false,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      let result;
      if (clubbingType === 'minorChild') {
        result = await advancedTaxApi.computeMinorChildClubbing(minorChildData);
      } else {
        result = await advancedTaxApi.computeSpouseClubbing(spouseData);
      }
      onResult(result);
      toast.success('Clubbing calculated');
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Clubbing Provisions</h3>
      
      <div style={{ display: 'grid', gap: 16 }}>
        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Clubbing Type
          </label>
          <select
            value={clubbingType}
            onChange={(e) => setClubbingType(e.target.value as any)}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          >
            <option value="minorChild">Minor Child (Section 64(1A))</option>
            <option value="spouse">Spouse (Section 64(1)(iv))</option>
          </select>
        </div>

        {clubbingType === 'minorChild' ? (
          <>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
                Child Income
              </label>
              <IndianNumberInput
                value={minorChildData.childIncome}
                onChange={(v) => setMinorChildData({ ...minorChildData, childIncome: v })}
                style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
                Number of Minor Children
              </label>
              <IndianNumberInput
                value={minorChildData.numberOfMinorChildren}
                onChange={(v) => setMinorChildData({ ...minorChildData, numberOfMinorChildren: v })}
                style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
                Parent 1 Income
              </label>
              <IndianNumberInput
                value={minorChildData.parent1Income}
                onChange={(v) => setMinorChildData({ ...minorChildData, parent1Income: v })}
                style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
                Parent 2 Income
              </label>
              <IndianNumberInput
                value={minorChildData.parent2Income}
                onChange={(v) => setMinorChildData({ ...minorChildData, parent2Income: v })}
                style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
              />
            </div>
          </>
        ) : (
          <>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
                Spouse Income
              </label>
              <IndianNumberInput
                value={spouseData.spouseIncome}
                onChange={(v) => setSpouseData({ ...spouseData, spouseIncome: v })}
                style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
              />
            </div>
            <div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                <input
                  type="checkbox"
                  checked={spouseData.adequateConsideration}
                  onChange={(e) => setSpouseData({ ...spouseData, adequateConsideration: e.target.checked })}
                />
                Adequate Consideration Paid
              </label>
            </div>
          </>
        )}

        <button
          type="submit"
          style={{
            padding: '10px 16px',
            background: 'var(--gold)',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Calculate Clubbing
        </button>
      </div>
    </form>
  );
}

function FOTradingCalculator({ onResult, setLoading }: any) {
  const [formData, setFormData] = useState({
    totalProfit: 0,
    totalLoss: 0,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const result = await advancedTaxApi.computeFOTrading(formData);
      onResult(result);
      toast.success('F&O trading calculated');
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>F&O Trading Income</h3>
      
      <div style={{ display: 'grid', gap: 16 }}>
        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Total Profit
          </label>
          <IndianNumberInput
            value={formData.totalProfit}
            onChange={(v) => setFormData({ ...formData, totalProfit: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Total Loss
          </label>
          <IndianNumberInput
            value={formData.totalLoss}
            onChange={(v) => setFormData({ ...formData, totalLoss: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <button
          type="submit"
          style={{
            padding: '10px 16px',
            background: 'var(--gold)',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Calculate F&O Income
        </button>
      </div>
    </form>
  );
}

function BreakEvenCalculator({ onResult, setLoading }: any) {
  const [formData, setFormData] = useState({
    grossIncome: 0,
    currentDeductions: 0,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const result = await advancedTaxApi.analyzeBreakEven(formData);
      onResult(result);
      toast.success('Break-even analysis completed');
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Break-Even Analysis (Old vs New Regime)</h3>
      
      <div style={{ display: 'grid', gap: 16 }}>
        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Gross Income
          </label>
          <IndianNumberInput
            value={formData.grossIncome}
            onChange={(v) => setFormData({ ...formData, grossIncome: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Current Deductions (80C, 80D, etc.)
          </label>
          <IndianNumberInput
            value={formData.currentDeductions}
            onChange={(v) => setFormData({ ...formData, currentDeductions: v })}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
          />
        </div>

        <button
          type="submit"
          style={{
            padding: '10px 16px',
            background: 'var(--gold)',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Analyze Break-Even
        </button>
      </div>
    </form>
  );
}
