import React, { useEffect, useMemo, useState } from 'react';

/** Canonical JSON value accepted by the ITR-3 auxiliary schedule editor. */
export type ITR3AuxiliaryValue = null | boolean | number | string | ITR3AuxiliaryValue[] | { [key: string]: ITR3AuxiliaryValue };
export type ITR3AuxiliaryData = Record<string, ITR3AuxiliaryValue>;

/** Props for the AY 2026-27 ITR-3 auxiliary schedule manager. */
export interface ITR3BusinessAuxiliaryManagerProps {
  data?: Partial<ITR3AuxiliaryData>;
  onChange: (data: ITR3AuxiliaryData) => void;
  visibleSchedules?: string[];
  showHeading?: boolean;
}

type Kind = 'money' | 'signed' | 'number' | 'text' | 'date' | 'select' | 'readonly';
interface Field { key: string; label?: string; kind?: Kind; options?: readonly string[]; max?: number; }
interface Group { key: string; label: string; fields?: readonly Field[]; groups?: readonly Group[]; rows?: RowSpec; }
interface RowSpec { fields: readonly Field[]; min?: number; max?: number; }
interface ScheduleSpec { key: string; label: string; groups?: readonly Group[]; fields?: readonly Field[]; }

type Obj = Record<string, ITR3AuxiliaryValue>;
const MAX = 99999999999999;
const AY10 = Array.from({ length: 22 }, (_, i) => `${2001 + i}-${String(2 + i).padStart(2, '0')}`);
const UNITS = ['101','102','103','104','105','106','107','108','109','110','111','112','113','114','115','116','117','118','119','120','121','122','999'] as const;
const UNIT_LABELS: Record<string, string> = {101:'Gms',102:'Kilograms',103:'Litre',104:'Kilolitre',105:'Metre',106:'Kilometre',107:'Numbers',108:'Quintal',109:'Ton',110:'Pound',111:'Milligrams',112:'Carat',113:'Numbers (1000s)',114:'Kwatt',115:'Mwatt',116:'Inch',117:'Feet',118:'Sqft',119:'Acre',120:'Cubicft',121:'Sqmetre',122:'Cubicmetre',999:'Residual'};
const input: React.CSSProperties = { width: '100%', boxSizing: 'border-box', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, color: 'var(--text-primary)', background: '#fff' };
const grid: React.CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 16 };
const addButton: React.CSSProperties = { padding: '6px 12px', background: 'var(--gold)', color: '#fff', border: 'none', borderRadius: 6, fontSize: 12, cursor: 'pointer' };
const removeButton: React.CSSProperties = { padding: '4px 8px', background: 'var(--danger)', color: '#fff', border: 'none', borderRadius: 4, fontSize: 11, cursor: 'pointer' };
const panel: React.CSSProperties = { border: '1px solid var(--border)', borderRadius: 6, padding: 16, marginTop: 12, background: 'var(--bg)' };

const f = (key: string, label?: string, kind: Kind = 'money', options?: readonly string[]): Field => ({ key, label: label || key, kind, options });
const moneyFields = (keys: readonly string[], readonly: readonly string[] = []): Field[] => keys.map((key) => f(key, undefined, readonly.includes(key) ? 'readonly' : (key.includes('CapGain') || key.includes('FirmCap') || key.includes('ProfitShareAmt') ? 'signed' : 'money')));
const depKeys = ['WDVFirstDay','AdjustmentSec115BAC','Total','AdditionsGrThan180Days','RealizationTotalPeriod','FullRateDeprAmt','AdditionsLessThan180Days','RealizationPeriodLessThan180days','HalfRateDeprAmt','DepreciationAtFullRate','DepreciationAtHalfRate','AddlnDeprOnGT180DayAdditions','AddlnDeprOnLessThan180DayAdditions','AddlnDeprOnAssetLessThan180Days','TotalDepreciation','DepDisAllowUs38_2','NetAggregateDepreciation','ProportionateAggDepreciation','ExpdrOnTrforSaleAsset','CapGainUs50','WDVLastDay'] as const;
const dep45Keys = ['WDVFirstDay','AdjustmentSec115BAC','Total','RealizationTotalPeriod','FullRateDeprAmt','DepreciationAtFullRate','TotalDepreciation','DepDisAllowUs38_2','NetAggregateDepreciation','ProportionateAggDepreciation','ExpdrOnTrforSaleAsset','CapGainUs50','WDVLastDay'] as const;
const doaKeys = ['WDVFirstDay','AdditionsGrThan180Days','RealizationTotalPeriod','FullRateDeprAmt','AdditionsLessThan180Days','RealizationPeriodLessThan180days','HalfRateDeprAmt','DepreciationAtFullRate','DepreciationAtHalfRate','TotalDepreciation','DepDisAllowUs38_2','NetAggregateDepreciation','ProportionateAggDepreciation','ExpdrOnTrforSaleAsset','CapGainUs50','WDVLastDay'] as const;
const block = (key: string, label: string, keys: readonly string[]): Group => ({ key, label, groups: [{ key: 'DepreciationDetail', label: 'DepreciationDetail', fields: moneyFields(keys, ['Total','FullRateDeprAmt','HalfRateDeprAmt','TotalDepreciation','NetAggregateDepreciation','WDVLastDay']) }] });
const deductionRows: RowSpec = { min: 1, fields: [f('DeductAmountSec80')] };
const undertaking = (key: string, label: string, code: string): Group => ({ key, label, fields: [f('Sch80LocOrDescCode','Sch80LocOrDescCode','readonly')], rows: { ...deductionRows }, groups: [{ key: '__code', label: code }] });
const qdBase = [f('ItemName','ItemName','text'),f('UnitOfMeasure','UnitOfMeasure','select',UNITS),f('OpeningStock'),f('PurchaseQty')];
const qdEnd = [f('SaleQty'),f('ClgStock'),f('AnyShortExces','AnyShortExces','signed')];
const address: Group = { key: 'AddressDetail', label: 'AddressDetail', fields: [f('AddrDetail','AddrDetail','text'),f('CityOrTownOrDistrict','CityOrTownOrDistrict','text'),f('StateCode','StateCode','select',Array.from({length:37},(_,i)=>String(i+1).padStart(2,'0'))),f('PinCode','PinCode','number')] };

const specs: readonly ScheduleSpec[] = [
  { key:'ScheduleDPM', label:'Schedule DPM — Plant and machinery', groups:[{key:'PlantMachinery',label:'PlantMachinery',groups:[block('Rate15','Rate15 (15%)',depKeys),block('Rate30','Rate30 (30%)',depKeys),block('Rate40','Rate40 (40%)',depKeys),block('Rate45','Rate45 — special block (45%)',dep45Keys)]}]},
  { key:'ScheduleDOA', label:'Schedule DOA — Other assets', groups:[
    {key:'Land',label:'Land',groups:[{key:'DepreciationDetail',label:'DepreciationDetail',fields:moneyFields(['WDVFirstDay','WDVLastDay'])}]},
    {key:'Building',label:'Building',groups:[block('Rate5','Rate5 (5%)',doaKeys),block('Rate10','Rate10 (10%)',doaKeys),block('Rate40','Rate40 (40%)',doaKeys)]},
    {key:'FurnitureFittings',label:'FurnitureFittings',groups:[block('Rate10','Rate10 (10%)',doaKeys)]},
    {key:'IntangibleAssets',label:'IntangibleAssets',groups:[block('Rate25','Rate25 (25%)',doaKeys)]},
    {key:'Ships',label:'Ships',groups:[block('Rate20','Rate20 (20%)',doaKeys)]}
  ]},
  { key:'ScheduleDEP', label:'Schedule DEP — Depreciation summary', groups:[{key:'SummaryFromDeprSch',label:'SummaryFromDeprSch',groups:[
    {key:'PlantMachinerySummary',label:'PlantMachinerySummary',fields:moneyFields(['DeprBlockTot15Percent','DeprBlockTot30Percent','DeprBlockTot40Percent','DeprBlockTot45Percent','TotPlntMach'],['DeprBlockTot15Percent','DeprBlockTot30Percent','DeprBlockTot40Percent','DeprBlockTot45Percent','TotPlntMach'])},
    {key:'BuildingSummary',label:'BuildingSummary',fields:moneyFields(['DeprBlockTot5Percent','DeprBlockTot10Percent','DeprBlockTot40Percent','TotBuildng'],['DeprBlockTot5Percent','DeprBlockTot10Percent','DeprBlockTot40Percent','TotBuildng'])}],fields:moneyFields(['FurnitureSummary','IntangibleAssetSummary','ShipsSummary','TotalDepreciation'],['FurnitureSummary','IntangibleAssetSummary','ShipsSummary','TotalDepreciation'])}]},
  { key:'ScheduleDCG', label:'Schedule DCG — Capital gains depreciation summary', groups:[{key:'SummaryFromDeprSchCG',label:'SummaryFromDeprSchCG',groups:[
    {key:'PlantMachinerySummaryCG',label:'PlantMachinerySummaryCG',fields:moneyFields(['DeprBlockTot15Percent','DeprBlockTot30Percent','DeprBlockTot40Percent','DeprBlockTot45Percent','TotPlntMach'],['TotPlntMach'])},
    {key:'BuildingSummaryCG',label:'BuildingSummaryCG',fields:moneyFields(['DeprBlockTot5Percent','DeprBlockTot10Percent','DeprBlockTot40Percent','TotBuildng'],['TotBuildng'])}],fields:moneyFields(['FurnitureSummary','IntangibleAssetSummary','ShipsSummary','TotalDepreciation'],['TotalDepreciation'])}]},
  { key:'ScheduleESR', label:'Schedule ESR — Expenditure on scientific research', groups:[{key:'DeductionUs35',label:'DeductionUs35',groups:['Section35_1_i','Section35_1_ii','Section35_1_iia','Section35_1_iii','Section35_1_iv','Section35_2AA','Section35_2AB','Section35_CCC','Section35_CCD','TotUs35'].map(key=>({key,label:key,groups:[{key:'DeductUs35',label:'DeductUs35',fields:moneyFields(['AmtDebPL','AmtUs35Allowable','ExcessAmtOverDebPL'],key==='TotUs35'?['AmtDebPL','AmtUs35Allowable','ExcessAmtOverDebPL']:[])}]}))}]},
  { key:'ITR3ScheduleUD', label:'Schedule UD — Unabsorbed depreciation', fields:[f('CurrAssYr','CurrAssYr','readonly'),...moneyFields(['CurBalCFNY','CurAllowBalCFNY','TotBFUDepritAmt','TotAdjustAccTax115BACAmt','TotCurYrdepritSetoffInc','TotDepritBalCFNY','TotBFUAllowAmt','TotCurYrAllowSetoffInc','TotalBalCFNY'],['TotBFUDepritAmt','TotAdjustAccTax115BACAmt','TotCurYrdepritSetoffInc','TotDepritBalCFNY','TotBFUAllowAmt','TotCurYrAllowSetoffInc','TotalBalCFNY'])],groups:[{key:'ScheduleUD',label:'Assessment-year rows',rows:{fields:[f('AssYr','AssYr','text'),...moneyFields(['AmtBFUD','AdjustAccTax115BACAmt','AmtDeprSOCY','BalCFNY','AmtBFUAllow','AmtAllowSOCY','AllowBalCFNY'],['BalCFNY','AllowBalCFNY'])]}}]},
  { key:'ScheduleICDS', label:'Schedule ICDS — Ten standards', groups:['AccPolicyAmtDetl','InventoriesValueDetl','ConstContractsAmtDetl','RevenueRcgAmtDetl','TangibleFixedAssetDetl','ForeignExgRatesDetl','GovtGrantsDetl','SecuritiesDetl','BorrowingCostsDetl','ProvAssetsDetl','TotalNetAmtDetl'].map(key=>({key,label:key,fields:moneyFields(key==='TotalNetAmtDetl'?['IncreaseInProfit','DecreaseInProfit']:['IncreaseInProfit','DecreaseInProfit','NetEffect'],key==='TotalNetAmtDetl'?['IncreaseInProfit','DecreaseInProfit']:['NetEffect'])}))},
  { key:'ScheduleGST', label:'Schedule GST', groups:[{key:'TurnoverGrsRcptForGSTIN',label:'Turnover / gross receipts by GSTIN',rows:{fields:[f('GSTINNo','GSTINNo','text'),f('AmtTurnGrossRcptGSTIN')]}}]},
  { key:'ScheduleIF', label:'Schedule IF — Partnership firms', groups:[{key:'PartnerFirmDetails',label:'PartnerFirmDetails',rows:{min:1,fields:[f('FirmName','FirmName','text'),f('FirmPAN','FirmPAN','text'),f('IsLiableToAudit','IsLiableToAudit','select',['Y','N']),f('Sec92EFirmFlag','Sec92EFirmFlag','select',['Y','N']),f('ProfitSharePercent','ProfitSharePercent','number'),f('ProfitShareAmt','ProfitShareAmt','signed'),f('IntrstAmtDueOrRecv'),f('RemunernAmtDueOrRecv'),f('FirmCapBalOn31Mar','FirmCapBalOn31Mar','signed')]}}],fields:moneyFields(['TotalProfitShareAmt','TotalIntrstAmtDueOrRecv','TotalRemunernAmtDueOrRecv','TotalFirmCapBalOn31Mar'],['TotalProfitShareAmt','TotalIntrstAmtDueOrRecv','TotalRemunernAmtDueOrRecv','TotalFirmCapBalOn31Mar'])},
  { key:'Schedule10AA', label:'Schedule 10AA', groups:[{key:'DeductSEZ',label:'DeductSEZ',groups:[{key:'DedUs10Detail',label:'DedUs10Detail',groups:[{key:'Undertaking',label:'Undertaking',groups:[{key:'DedFromUndertakingWithAy',label:'DedFromUndertakingWithAy',rows:{min:1,fields:[f('AssmtYrUnit','AssmtYrUnit','select',AY10),f('DedUs10Sub')]}}]}],fields:[f('TotalDedUs10Sub','TotalDedUs10Sub','readonly')]}]}]},
  { key:'Schedule80_IA', label:'Schedule 80-IA', fields:[f('Sch80SectionCode','Sch80SectionCode','readonly'),f('TotSchedule80_IA','TotSchedule80_IA','readonly')],groups:[undertaking('DeductUs80_IA_4_iv','DeductUs80_IA_4_iv','POWER')]},
  { key:'Schedule80_IB', label:'Schedule 80-IB', fields:[f('Sch80SectionCode','Sch80SectionCode','readonly'),f('TotSchedule80_IB','TotSchedule80_IB','readonly')],groups:[undertaking('DeductMinOilUs80_IB_9_Und','Mineral oil','COMM_PROD'),undertaking('DeductHousUs80_IB_10_Und','Housing','HOUSING_PROJECT'),undertaking('DeductFruitVegUs80_IB_11A_Und','Fruit / vegetables','FRIUTS_VEGTBLE'),undertaking('DeductFoodGrainUs80_IB_11A_Und','Food grain','STOR_TRANS')]},
  { key:'Schedule80_IC', label:'Schedule 80-IC / IE', fields:[f('Sch80SectionCode','Sch80SectionCode','readonly'),f('TotSchedule80_IC','TotSchedule80_IC','readonly')],groups:[{key:'DeductInNorthEast',label:'DeductInNorthEast',groups:[undertaking('Assam_Und','Assam','INDSRTL_ASSAM'),undertaking('ArunachalPradesh_Und','Arunachal Pradesh','INDSRTL_ARUNPRADESH'),undertaking('Manipur_Und','Manipur','INDSRTL_MANIPUR'),undertaking('Mizoram_Und','Mizoram','INDSRTL_MIZORAM'),undertaking('Meghalaya_Und','Meghalaya','INDSRTL_MEGHALAYA'),undertaking('Nagaland_Und','Nagaland','INDSRTL_NAGALND'),undertaking('Tripura_Und','Tripura','INDSRTL_TRIPURA'),undertaking('Sikkim_Und','Sikkim','INDSRTL_SIKKIM')],fields:[f('TotDeductInNorthEast','TotDeductInNorthEast','readonly')]}]},
  { key:'Schedule80RA', label:'Schedule 80RA', fields:moneyFields(['TotalDonationAmtCash80RA','TotalDonationAmtOtherMode80RA','TotalDonationsUs80RA','TotalEligibleDonationAmt80RA'],['TotalDonationAmtCash80RA','TotalDonationAmtOtherMode80RA','TotalDonationsUs80RA','TotalEligibleDonationAmt80RA']),groups:[{key:'DonationDtlsRsrchAssctn',label:'DonationDtlsRsrchAssctn',rows:{fields:[f('NameOfDonee','NameOfDonee','text'),f('DoneePAN','DoneePAN','text'),f('DonationAmtCash'),f('DonationAmtOtherMode'),f('DonationAmt','DonationAmt','readonly'),f('EligibleDonationAmt')]},groups:[address]}]},
  { key:'ScheduleTPSA', label:'Schedule TPSA', fields:[...moneyFields(['AmtPrimaryAdjUs92CE_2A','AdditionalIncTax18PercAbove','Surcharge12Perc','HealthEducationCess','TotalAdditionalTax','TaxesPaid','NetTaxPayable','TotalAmountDeposited'],['TotalAdditionalTax','NetTaxPayable','TotalAmountDeposited'])],groups:[{key:'DtlsTaxesPaid',label:'DtlsTaxesPaid',rows:{fields:[f('BSRCode','BSRCode','text'),f('BankBranchName','BankBranchName','text'),f('DateDep','DateDep','date'),f('SrlNoOfChaln','SrlNoOfChaln','number'),f('Amount')]}}]},
  { key:'PARTA_QD', label:'Part A-QD — Quantitative details', groups:[{key:'TradingConcern',label:'TradingConcern',groups:[{key:'QuantitDet',label:'QuantitDet (1–20)',rows:{min:1,max:20,fields:[...qdBase,...qdEnd]}}]},{key:'ManfactrConcern',label:'ManfactrConcern',groups:[{key:'RawMaterial',label:'RawMaterial',groups:[{key:'QuantitDet',label:'QuantitDet (1–20)',rows:{min:1,max:20,fields:[...qdBase,f('PrevYrConsum'),...qdEnd,f('yldFinisProd'),f('PercentYld','PercentYld','number')]}}]},{key:'FinishrByProd',label:'FinishrByProd',groups:[{key:'QuantitDet',label:'QuantitDet (1–20)',rows:{min:1,max:20,fields:[...qdBase,f('PrevyrManfact'),...qdEnd]}}]}]}]}
];

const asObj = (value: ITR3AuxiliaryValue | undefined): Obj => value && typeof value === 'object' && !Array.isArray(value) ? value as Obj : {};
const n = (value: ITR3AuxiliaryValue | undefined): number => typeof value === 'number' && Number.isFinite(value) ? value : 0;
const sum = (rows: ITR3AuxiliaryValue[], key: string): number => rows.reduce<number>((total,row)=>total+n(asObj(row)[key]),0);
const deepClone = (value: ITR3AuxiliaryData): ITR3AuxiliaryData => JSON.parse(JSON.stringify(value)) as ITR3AuxiliaryData;
const pathGet = (root: Obj, path: readonly (string|number)[]): ITR3AuxiliaryValue | undefined => path.reduce<ITR3AuxiliaryValue|undefined>((v,k)=>Array.isArray(v)?v[Number(k)]:asObj(v)[String(k)],root);
const pathSet = (root: Obj, path: readonly (string|number)[], value: ITR3AuxiliaryValue): void => { let cursor: ITR3AuxiliaryValue = root; path.forEach((key,index)=>{ const last=index===path.length-1; if(Array.isArray(cursor)){ if(last) cursor[Number(key)]=value; else { cursor[Number(key)] ??= typeof path[index+1]==='number'?[]:{}; cursor=cursor[Number(key)]; } } else { const obj=asObj(cursor); if(last) obj[String(key)]=value; else { obj[String(key)] ??= typeof path[index+1]==='number'?[]:{}; cursor=obj[String(key)]; } } }); };
const at = (root: Obj, path: readonly (string|number)[]): Obj => asObj(pathGet(root,path));
const humanize = (name: string): string => {
  const replacements: Record<string,string> = {Tot:'Total',Amt:'Amount',Inc:'Income',Exp:'Expense',Dtls:'Details',Dtl:'Detail',Stck:'Stock',Opng:'Opening',Clsng:'Closing',Bal:'Balance',Curr:'Current',Prev:'Previous',Yr:'Year',Bus:'Business',Prof:'Profession',Depr:'Depreciation',Deduct:'Deduction',Adj:'Adjustment',Rcpt:'Receipt',Grs:'Gross',Oth:'Other',Sec:'Section',Assmt:'Assessment',Addr:'Address',Qty:'Quantity'};
  return name.replace(/([a-z0-9])([A-Z])/g,'$1 $2').replace(/_/g,' ').split(' ').map(token=>replacements[token]??token).join(' ').replace(/\s+/g,' ').trim();
};
const FRIENDLY_LABELS: Record<string, string> = {
  PlantMachinery: 'Plant and machinery',
  DepreciationDetail: 'Block-wise depreciation computation',
  SummaryFromDeprSch: 'Depreciation summary carried to Schedule BP',
  SummaryFromDeprSchCG: 'Section 50 capital-gains summary',
  DeductionUs35: 'Deduction under section 35',
  DeductUs35: 'Scientific research expenditure and eligible deduction',
  ScheduleUD: 'Assessment-year-wise unabsorbed depreciation',
  AccPolicyAmtDetl: 'ICDS I — Accounting policies',
  InventoriesValueDetl: 'ICDS II — Valuation of inventories',
  ConstContractsAmtDetl: 'ICDS III — Construction contracts',
  RevenueRcgAmtDetl: 'ICDS IV — Revenue recognition',
  TangibleFixedAssetDetl: 'ICDS V — Tangible fixed assets',
  ForeignExgRatesDetl: 'ICDS VI — Effects of changes in foreign exchange rates',
  GovtGrantsDetl: 'ICDS VII — Government grants',
  SecuritiesDetl: 'ICDS VIII — Securities',
  BorrowingCostsDetl: 'ICDS IX — Borrowing costs',
  ProvAssetsDetl: 'ICDS X — Provisions, contingent liabilities and contingent assets',
  TotalNetAmtDetl: 'Total ICDS adjustment',
  TurnoverGrsRcptForGSTIN: 'Turnover or gross receipts by GSTIN',
  PartnerFirmDetails: 'Partnership-firm details',
  DeductSEZ: 'Eligible SEZ undertakings',
  DedUs10Detail: 'Deduction under section 10AA',
  Undertaking: 'Undertaking-wise deduction',
  DedFromUndertakingWithAy: 'Assessment-year-wise deduction',
  DeductInNorthEast: 'Eligible undertakings in the North-East',
  DonationDtlsRsrchAssctn: 'Research-association donation details',
  DtlsTaxesPaid: 'Additional-tax payment details',
  TradingConcern: 'Trading concern — quantitative details',
  ManfactrConcern: 'Manufacturing concern — quantitative details',
  RawMaterial: 'Raw materials',
  FinishrByProd: 'Finished goods and by-products',
  QuantitDet: 'Item-wise quantity details',
  WDVFirstDay: 'Written-down value on 1 April 2025',
  WDVLastDay: 'Written-down value on 31 March 2026',
  AdditionsGrThan180Days: 'Additions used for 180 days or more',
  AdditionsLessThan180Days: 'Additions used for less than 180 days',
  TotalDepreciation: 'Total depreciation',
  NetAggregateDepreciation: 'Net aggregate depreciation',
  AssYr: 'Assessment year',
  FirmName: 'Name of firm',
  FirmPAN: 'PAN of firm',
  IsLiableToAudit: 'Is the firm liable to audit?',
  Sec92EFirmFlag: 'Is the firm liable under section 92E?',
  ProfitSharePercent: 'Share of profit (%)',
  ProfitShareAmt: 'Share of profit amount',
  IntrstAmtDueOrRecv: 'Interest due or received',
  RemunernAmtDueOrRecv: 'Remuneration due or received',
  FirmCapBalOn31Mar: 'Capital balance on 31 March 2026',
  GSTINNo: 'GSTIN',
  AmtTurnGrossRcptGSTIN: 'Turnover or gross receipts',
  ItemName: 'Item name',
  UnitOfMeasure: 'Unit of measure',
  OpeningStock: 'Opening stock quantity',
  PurchaseQty: 'Purchase quantity',
  SaleQty: 'Sales quantity',
  ClgStock: 'Closing stock quantity',
  AnyShortExces: 'Shortage or excess',
};
const fieldLabel = (field: Field): string => field.label && field.label !== field.key ? field.label : FRIENDLY_LABELS[field.key] ?? humanize(field.key);
const groupLabel = (group: Group): string => FRIENDLY_LABELS[group.key] ?? (group.label === group.key ? humanize(group.label) : group.label);

interface AuxiliaryStats { populated: number; rows: number; total: number; }
const auxiliaryStats = (value: ITR3AuxiliaryValue | undefined): AuxiliaryStats => {
  if (Array.isArray(value)) return value.reduce<AuxiliaryStats>((stats, item) => { const child = auxiliaryStats(item); return { populated: stats.populated + child.populated, rows: stats.rows + child.rows, total: stats.total + child.total }; }, { populated: 0, rows: value.length, total: 0 });
  if (value && typeof value === 'object') return Object.entries(value).reduce<AuxiliaryStats>((stats, [key, item]) => { const child = auxiliaryStats(item); const includeTotal = typeof item === 'number' && !/(^Tot|Total|BalCFNY|Net|WDVLastDay|FullRate|HalfRate)/.test(key); return { populated: stats.populated + child.populated, rows: stats.rows + child.rows, total: stats.total + child.total + (includeTotal ? item : 0) }; }, { populated: 0, rows: 0, total: 0 });
  return { populated: value !== '' && value !== null && value !== undefined && value !== 0 && value !== false ? 1 : 0, rows: 0, total: 0 };
};
const scheduleSummary = (value: ITR3AuxiliaryValue | undefined): string => { const stats = auxiliaryStats(value); return `${stats.populated} field${stats.populated === 1 ? '' : 's'} entered${stats.rows ? ` · ${stats.rows} row${stats.rows === 1 ? '' : 's'}` : ''}${stats.total ? ` · ₹${stats.total.toLocaleString('en-IN')}` : ''}`; };

function recompute(source: ITR3AuxiliaryData): ITR3AuxiliaryData {
  const d=deepClone(source); const root=d as Obj;
  const dep=(schedule:string,path:string[]):Obj=>at(root,[schedule,...path,'DepreciationDetail']);
  for(const rate of ['Rate15','Rate30','Rate40']){ const x=dep('ScheduleDPM',['PlantMachinery',rate]); x.Total=n(x.WDVFirstDay)+n(x.AdjustmentSec115BAC); x.FullRateDeprAmt=n(x.Total)+n(x.AdditionsGrThan180Days)-n(x.RealizationTotalPeriod); x.HalfRateDeprAmt=n(x.AdditionsLessThan180Days)-n(x.RealizationPeriodLessThan180days); x.TotalDepreciation=n(x.DepreciationAtFullRate)+n(x.DepreciationAtHalfRate)+n(x.AddlnDeprOnGT180DayAdditions)+n(x.AddlnDeprOnLessThan180DayAdditions)+n(x.AddlnDeprOnAssetLessThan180Days); x.NetAggregateDepreciation=n(x.TotalDepreciation)-n(x.DepDisAllowUs38_2); x.WDVLastDay=n(x.FullRateDeprAmt)+n(x.HalfRateDeprAmt)-n(x.TotalDepreciation)-n(x.ExpdrOnTrforSaleAsset); }
  const x45=dep('ScheduleDPM',['PlantMachinery','Rate45']); x45.Total=n(x45.WDVFirstDay)+n(x45.AdjustmentSec115BAC); x45.FullRateDeprAmt=n(x45.Total)-n(x45.RealizationTotalPeriod); x45.TotalDepreciation=n(x45.DepreciationAtFullRate); x45.NetAggregateDepreciation=n(x45.TotalDepreciation)-n(x45.DepDisAllowUs38_2); x45.WDVLastDay=n(x45.FullRateDeprAmt)-n(x45.TotalDepreciation)-n(x45.ExpdrOnTrforSaleAsset);
  const doaPaths=[['Building','Rate5'],['Building','Rate10'],['Building','Rate40'],['FurnitureFittings','Rate10'],['IntangibleAssets','Rate25'],['Ships','Rate20']]; for(const p of doaPaths){const x=dep('ScheduleDOA',p); x.FullRateDeprAmt=n(x.WDVFirstDay)+n(x.AdditionsGrThan180Days)-n(x.RealizationTotalPeriod);x.HalfRateDeprAmt=n(x.AdditionsLessThan180Days)-n(x.RealizationPeriodLessThan180days);x.TotalDepreciation=n(x.DepreciationAtFullRate)+n(x.DepreciationAtHalfRate);x.NetAggregateDepreciation=n(x.TotalDepreciation)-n(x.DepDisAllowUs38_2);x.WDVLastDay=n(x.FullRateDeprAmt)+n(x.HalfRateDeprAmt)-n(x.TotalDepreciation)-n(x.ExpdrOnTrforSaleAsset);}
  const esr=at(root,['ScheduleESR','DeductionUs35']); const sections=['Section35_1_i','Section35_1_ii','Section35_1_iia','Section35_1_iii','Section35_1_iv','Section35_2AA','Section35_2AB','Section35_CCC','Section35_CCD']; const tot=at(esr,['TotUs35','DeductUs35']); for(const k of ['AmtDebPL','AmtUs35Allowable','ExcessAmtOverDebPL']) tot[k]=sections.reduce((s,key)=>s+n(at(esr,[key,'DeductUs35'])[k]),0);
  const ud=at(root,['ITR3ScheduleUD']); ud.CurrAssYr='2026-27'; const udRows=(ud.ScheduleUD as ITR3AuxiliaryValue[])||[]; for(const rowV of udRows){const row=asObj(rowV);row.BalCFNY=Math.max(0,n(row.AmtBFUD)+n(row.AdjustAccTax115BACAmt)-n(row.AmtDeprSOCY));row.AllowBalCFNY=Math.max(0,n(row.AmtBFUAllow)-n(row.AmtAllowSOCY));} ud.TotBFUDepritAmt=sum(udRows,'AmtBFUD');ud.TotAdjustAccTax115BACAmt=sum(udRows,'AdjustAccTax115BACAmt');ud.TotCurYrdepritSetoffInc=sum(udRows,'AmtDeprSOCY');ud.TotDepritBalCFNY=sum(udRows,'BalCFNY')+n(ud.CurBalCFNY);ud.TotBFUAllowAmt=sum(udRows,'AmtBFUAllow');ud.TotCurYrAllowSetoffInc=sum(udRows,'AmtAllowSOCY');ud.TotalBalCFNY=sum(udRows,'AllowBalCFNY')+n(ud.CurAllowBalCFNY);
  const icds=at(root,['ScheduleICDS']); const icdsKeys=['AccPolicyAmtDetl','InventoriesValueDetl','ConstContractsAmtDetl','RevenueRcgAmtDetl','TangibleFixedAssetDetl','ForeignExgRatesDetl','GovtGrantsDetl','SecuritiesDetl','BorrowingCostsDetl','ProvAssetsDetl'];for(const key of icdsKeys){const o=at(icds,[key]);o.NetEffect=n(o.IncreaseInProfit)-n(o.DecreaseInProfit);} const icTot=at(icds,['TotalNetAmtDetl']);icTot.IncreaseInProfit=icdsKeys.reduce((s,k)=>s+n(at(icds,[k]).IncreaseInProfit),0);icTot.DecreaseInProfit=icdsKeys.reduce((s,k)=>s+n(at(icds,[k]).DecreaseInProfit),0);
  const firm=at(root,['ScheduleIF']);const firms=(firm.PartnerFirmDetails as ITR3AuxiliaryValue[])||[];firm.TotalProfitShareAmt=sum(firms,'ProfitShareAmt');firm.TotalIntrstAmtDueOrRecv=sum(firms,'IntrstAmtDueOrRecv');firm.TotalRemunernAmtDueOrRecv=sum(firms,'RemunernAmtDueOrRecv');firm.TotalFirmCapBalOn31Mar=sum(firms,'FirmCapBalOn31Mar');
  const s10=at(root,['Schedule10AA','DeductSEZ','DedUs10Detail']);s10.TotalDedUs10Sub=sum((at(s10,['Undertaking']).DedFromUndertakingWithAy as ITR3AuxiliaryValue[])||[],'DedUs10Sub');
  const schedule80=(schedule:string,code:string,paths:string[][],totalKey:string):void=>{const o=at(root,[schedule]);o.Sch80SectionCode=code;let total=0;for(const p of paths){const u=at(o,p);const codeHolder=at(u,['__code']);if(typeof codeHolder.label==='string')u.Sch80LocOrDescCode=codeHolder.label; delete u.__code; total+=sum((u.Sch80DeductAmtDtls as ITR3AuxiliaryValue[])||[],'DeductAmountSec80');}o[totalKey]=total;};
  schedule80('Schedule80_IA','80-IA',[['DeductUs80_IA_4_iv']],'TotSchedule80_IA');schedule80('Schedule80_IB','80-IB',[['DeductMinOilUs80_IB_9_Und'],['DeductHousUs80_IB_10_Und'],['DeductFruitVegUs80_IB_11A_Und'],['DeductFoodGrainUs80_IB_11A_Und']],'TotSchedule80_IB'); const ne=['Assam_Und','ArunachalPradesh_Und','Manipur_Und','Mizoram_Und','Meghalaya_Und','Nagaland_Und','Tripura_Und','Sikkim_Und'].map(k=>['DeductInNorthEast',k]);schedule80('Schedule80_IC','80-IC_IE',ne,'TotSchedule80_IC');const neo=at(root,['Schedule80_IC','DeductInNorthEast']);neo.TotDeductInNorthEast=n(at(root,['Schedule80_IC']).TotSchedule80_IC);
  const ra=at(root,['Schedule80RA']);const donations=(ra.DonationDtlsRsrchAssctn as ITR3AuxiliaryValue[])||[];for(const v of donations){const o=asObj(v);o.DonationAmt=n(o.DonationAmtCash)+n(o.DonationAmtOtherMode);}ra.TotalDonationAmtCash80RA=sum(donations,'DonationAmtCash');ra.TotalDonationAmtOtherMode80RA=sum(donations,'DonationAmtOtherMode');ra.TotalDonationsUs80RA=sum(donations,'DonationAmt');ra.TotalEligibleDonationAmt80RA=sum(donations,'EligibleDonationAmt');
  const tp=at(root,['ScheduleTPSA']);tp.TotalAdditionalTax=n(tp.AdditionalIncTax18PercAbove)+n(tp.Surcharge12Perc)+n(tp.HealthEducationCess);tp.NetTaxPayable=Math.max(0,n(tp.TotalAdditionalTax)-n(tp.TaxesPaid));tp.TotalAmountDeposited=sum((tp.DtlsTaxesPaid as ITR3AuxiliaryValue[])||[],'Amount');
  return d;
}

function FieldEditor({ field, value, onValue }: { field: Field; value: ITR3AuxiliaryValue | undefined; onValue: (value: ITR3AuxiliaryValue) => void }): React.JSX.Element {
  const kind=field.kind||'money'; const label=fieldLabel(field); const numeric=['money','signed','number','readonly'].includes(kind); const min=kind==='signed'?undefined:0;
  return <label style={{display:'block',minWidth:0}}><span style={{display:'block',marginBottom:6,fontSize:12,fontWeight:500,color:'var(--text-secondary)'}}>{label}{field.key==='UnitOfMeasure'&&typeof value==='string'?` — ${UNIT_LABELS[value]||''}`:''}{kind==='readonly'?' (calculated)':''}</span>
    {kind==='select'?<select style={input} value={String(value??'')} onChange={e=>onValue(e.target.value)}><option value="">Select</option>{field.options?.map(o=><option key={o} value={o}>{o}{field.key==='UnitOfMeasure'?` — ${UNIT_LABELS[o]}`:''}</option>)}</select>:<input style={{...input,background:kind==='readonly'?'var(--gold-pale)':'#fff',fontWeight:kind==='readonly'?600:400}} type={kind==='date'?'date':numeric?'number':'text'} min={min} max={field.max??(numeric?MAX:undefined)} step={kind==='number'?'0.01':'1'} readOnly={kind==='readonly'} value={value===undefined||value===null?'':String(value)} onChange={e=>onValue(numeric?(e.target.value===''?0:Number(e.target.value)):e.target.value)} />}
  </label>;
}

function GroupEditor({ group, root, path, update, depth = 0 }: { group: Group; root: Obj; path: (string|number)[]; update: (path:(string|number)[],value:ITR3AuxiliaryValue)=>void; depth?: number }): React.JSX.Element {
  if(group.key==='__code') return <></>; const p=[...path,group.key]; const rows=group.rows?(pathGet(root,p) as ITR3AuxiliaryValue[]|undefined)||[]:[]; const groupValue=pathGet(root,p); const title=groupLabel(group);
  return <details open={depth===0} style={{...panel,background:depth===0?'var(--bg)':'#fff'}}><summary style={{cursor:'pointer',listStyle:'none',display:'flex',justifyContent:'space-between',alignItems:'center',gap:12}}><span style={{fontSize:13,fontWeight:600,color:'var(--text-secondary)'}}>{title}</span><span style={{fontSize:11,color:'var(--text-muted)',fontWeight:400}}>{scheduleSummary(groupValue)} · Expand / collapse</span></summary>
    <div style={{paddingTop:14}}>
      {group.fields&&<div style={grid}>{group.fields.map(field=><FieldEditor key={field.key} field={field} value={pathGet(root,[...p,field.key])} onValue={v=>update([...p,field.key],v)}/>)}</div>}
      {group.rows&&<div style={{marginTop:group.fields?16:0}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:12,marginBottom:rows.length?12:0}}><div style={{fontSize:11,color:'var(--text-muted)'}}>{rows.length} entr{rows.length===1?'y':'ies'}{group.rows.min?` · minimum ${group.rows.min}`:''}{group.rows.max?` · maximum ${group.rows.max}`:''}</div><button type="button" style={{...addButton,opacity:rows.length>=(group.rows.max??Infinity)?0.5:1}} disabled={rows.length>=(group.rows.max??Infinity)} onClick={()=>update(p,[...rows,Object.fromEntries(group.rows!.fields.map(x=>[x.key,x.kind==='text'||x.kind==='date'||x.kind==='select'?'':0]))])}>+ Add entry</button></div>
        {rows.length===0&&<div style={{padding:20,textAlign:'center',color:'var(--text-muted)',background:'#fff',borderRadius:6}}>No entries. Click “Add entry” to add one.</div>}
        {rows.map((row,index)=><div key={index} style={{background:'#fff',padding:16,border:'1px solid var(--border)',borderRadius:6,marginTop:12}}><div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:12,marginBottom:12}}><h4 style={{margin:0,fontSize:13,color:'var(--text-secondary)'}}>Entry #{index+1}</h4><button type="button" style={{...removeButton,opacity:rows.length<=(group.rows?.min||0)?0.5:1}} disabled={rows.length<=(group.rows?.min||0)} onClick={()=>update(p,rows.filter((_,i)=>i!==index))}>Remove</button></div><div style={grid}>{group.rows!.fields.map(field=><FieldEditor key={field.key} field={field} value={asObj(row)[field.key]} onValue={v=>update([...p,index,field.key],v)}/>)}</div>{group.groups?.map(g=><GroupEditor key={g.key} group={g} root={root} path={[...p,index]} update={update} depth={depth+1}/>)}</div>)}
      </div>}
      {group.groups?.map(g=><GroupEditor key={g.key} group={g} root={root} path={p} update={update} depth={depth+1}/>)}</div>
  </details>;
}

/** Renders canonical, frontend-only AY 2026-27 ITR-3 auxiliary schedules. */
export default function ITR3BusinessAuxiliaryManager({ data, onChange, visibleSchedules, showHeading = true }: ITR3BusinessAuxiliaryManagerProps): React.JSX.Element {
  const [draft,setDraft]=useState<ITR3AuxiliaryData>(()=>recompute((data||{}) as ITR3AuxiliaryData)); const [open,setOpen]=useState<Set<string>>(()=>new Set(visibleSchedules?.slice(0,1)??['ScheduleDPM']));
  useEffect(()=>{setDraft(recompute((data||{}) as ITR3AuxiliaryData));},[data]);
  useEffect(()=>setOpen(current=>current.size>0&&(!visibleSchedules||visibleSchedules.some(key=>current.has(key)))?current:new Set(visibleSchedules?.slice(0,1)??['ScheduleDPM'])),[visibleSchedules]);
  const canonical=useMemo(()=>recompute(draft),[draft]);
  const displayedSpecs=visibleSchedules?specs.filter(spec=>visibleSchedules.includes(spec.key)):specs;
  const update=(path:(string|number)[],value:ITR3AuxiliaryValue):void=>{const next=deepClone(draft);pathSet(next as Obj,path,value);const computed=recompute(next);setDraft(computed);onChange(computed);};
  const toggle=(key:string):void=>setOpen(current=>{const next=new Set(current);if(next.has(key))next.delete(key);else next.add(key);return next;});
  return <section aria-label="ITR-3 auxiliary business schedules">
    {showHeading&&<div style={{display:'flex',alignItems:'center',gap:8,margin:'24px 0 18px'}}><span style={{background:'var(--gold)',color:'#fff',padding:'4px 10px',borderRadius:4,fontSize:12,fontWeight:600}}>AUX</span><div><h3 style={{margin:0,fontSize:14,fontWeight:600,color:'var(--text-secondary)'}}>Supporting Business and Deduction Schedules</h3><div style={{marginTop:3,fontSize:11,color:'var(--text-muted)'}}>Official AY 2026-27 ITR-3 schedules · canonical fields and calculated totals</div></div></div>}
    {displayedSpecs.map((spec,index)=>{const isOpen=open.has(spec.key);const value=pathGet(canonical as Obj,[spec.key]);return <section key={spec.key} style={{marginBottom:16,background:'var(--bg)',border:'1px solid var(--border)',borderRadius:6,overflow:'hidden'}}>
      <button type="button" onClick={()=>toggle(spec.key)} aria-expanded={isOpen} style={{width:'100%',padding:16,border:0,background:'transparent',cursor:'pointer',textAlign:'left',display:'flex',justifyContent:'space-between',alignItems:'center',gap:16}}><span style={{display:'flex',alignItems:'center',gap:10}}><span style={{width:26,height:26,borderRadius:4,background:isOpen?'var(--gold)':'var(--gold-pale)',color:isOpen?'#fff':'var(--text-secondary)',display:'inline-flex',alignItems:'center',justifyContent:'center',fontSize:11,fontWeight:700}}>{index+1}</span><span><span style={{display:'block',fontSize:13,fontWeight:600,color:'var(--text-secondary)'}}>{spec.label}</span><span style={{display:'block',marginTop:4,fontSize:11,color:'var(--text-muted)'}}>{scheduleSummary(value)}</span></span></span><span style={{fontSize:12,color:'var(--text-muted)'}}>{isOpen?'Collapse ▲':'Expand ▼'}</span></button>
      {isOpen&&<div style={{padding:'0 16px 16px'}}>{spec.fields&&<div style={grid}>{spec.fields.map(field=><FieldEditor key={field.key} field={field} value={pathGet(canonical as Obj,[spec.key,field.key])} onValue={v=>update([spec.key,field.key],v)}/>)}</div>}{spec.groups?.map(group=><GroupEditor key={group.key} group={group} root={canonical as Obj} path={[spec.key]} update={update}/>)}</div>}
    </section>;})}
  </section>;
}
