import type { CanonicalJsonValue, ITR3BusinessWorkspace, Money } from './returns/types';

/** Official AY 2026-27 PARTA_OI source disclosures. */
export interface ITR3PartAOI {
  methodOfAcct: 'MERC' | 'CASH'; changeInAcctMethFlg: 'N' | 'Y';
  profDeviatDueAcctMeth: Money; decProOrIncLossUs145_2: Money;
  methodOfValClgStk: Record<string, Money | string>; noCredToPLAmt: Record<string, Money>;
  amountDisallUs36: Record<string, Money>; amountDisallUs37: Record<string, Money>;
  amountDisallUs40: Record<string, Money>; amountDisallUs40A: Record<string, Money>;
  amountDisallUs43BPrevious: Record<string, Money>; amountDisallUs43B: Record<string, Money>;
  amountExciseCustomsVATOutstanding: Record<string, Money>;
  deemedProfUs33ABs: Money; deemedProfUs33AB: Money; deemedProfUs33ABA: Money;
  profTaxAmtUs41: Money; priorAmtIncCrDrPL: Money; amountOfExpDisallwUs14A: Money;
  interestDisAllowUs23SMEAct: Money; scheduleTPSAFlg: 'N' | 'Y'; otherAdditions: Money; otherDeductions: Money;
}

const group36 = ['StkInsurPrem','EmpHealthInsurPrem','EmpBonusCommSum','IntOnBorrCap','ZeroCoupBondDisc','RecogPFContribAmt','AppSuperAnnFundAmt','PensionSchemeSec80CCD','AppGratFundAmt','OthFundAmt','EmpContributionCredits','BadDebtDoubtAmt','BadDebtDoubtProvn','SpecResrvTranfr','FamPlanPromoExp','SecuritiesPaidAmt','MrktLossOthExpLossICDS','OthDisallowances'];
const group37 = ['CapitalNatureExp','PersonalExp','BusOrProfessnExp','PoliticPartyExp','LawVoilatPenalExp','OthPenalFineExp','OffenceExp','ContigentLiability','OthAmtNotAllowUs37'];
const group40 = ['NonCompChapXVIIBAmt','NonComp40aiiChapXVIIBAmt','NonComp40aibChapXVIIBAmt','NonComp40aiiiChapXVIIBAmt','TaxAmtOnProfits','WTAmt','RolyatyOrServiceFee','IntSalBonPartner','OthDisallow','AmtDisallUs40PyNowAll'];
const group40A = ['AmtPaidUs40A2b','AmtGT20kCash','ProvPmtGrat','ContToSetupTrust','OthDisallow'];
const group43B = ['TaxDutyCesAmt','ContToEmpPFSFGF','EmpBonusComm','IntPayaleToFI','SumPayaleLoanBrToFinComp','IntPayaleToFISchBank','LeaveEncashPayable','RailwayAssetsPayable','MSEPayable'];
const excise = ['UnionExciseDuty','ServiceTax','VATorSaleTax','Cess','CentralGoodServiceTax','StateGoodServiceTax','IntegratedGoodServiceTax','UnionTerrGoodServiceTax','OthDutyTaxCess'];
const noCredit = ['Section28Items','ProformaCreditsDue','PrevYrEscalClaim','OthItemInc','CapReceipt'];
const computed = new Set(['TotAmtDisallUs36','TotAmtDisallUs37','TotAmtDisallUs40','TotAmtDisallUs40A','TotAmtUs43b','TotExciseCustomsVAT','TotNoCredToPLAmt']);
const numeric = (value: unknown): number => { const n = typeof value === 'number' ? value : Number(value); return Number.isFinite(n) && n >= 0 ? Math.floor(n) : 0; };
const entries = (group: keyof ITR3PartAOI, path: string, names: readonly string[]): PartAOIField[] => names.filter((name) => !computed.has(name)).map((name) => ({ key: name, path: `${path}.${name}`, label: name, group }));

export interface PartAOIField { key: string; path: string; label: string; group: keyof ITR3PartAOI; }
export const ITR3_PART_A_OI_FIELDS: readonly PartAOIField[] = [
  {key:'AmountOfExpDisAllwUs14A',path:'PARTA_OI.AmountOfExpDisAllwUs14A',label:'Section 14A expenditure disallowance',group:'amountOfExpDisallwUs14A'},
  {key:'DeemedProfUs33AB',path:'PARTA_OI.DeemedProfUs33AB',label:'Deemed income under section 33AB',group:'deemedProfUs33AB'},
  {key:'DeemedProfUs33ABA',path:'PARTA_OI.DeemedProfUs33ABA',label:'Deemed income under section 33ABA',group:'deemedProfUs33ABA'},
  {key:'DeemedProfUs33ABs',path:'PARTA_OI.DeemedProfUs33ABs',label:'Deemed income under section 33AB (other)',group:'deemedProfUs33ABs'},
  {key:'ProfTaxAmtUs41',path:'PARTA_OI.ProfTaxAmtUs41',label:'Professional tax under section 41',group:'profTaxAmtUs41'},
  {key:'InterestDisAllowUs23SMEAct',path:'PARTA_OI.InterestDisAllowUs23SMEAct',label:'MSME interest disallowance',group:'interestDisAllowUs23SMEAct'},
  {key:'PriorAmtIncCrDrPL',path:'PARTA_OI.PriorAmtIncCrDrPL',label:'Prior period income or loss credited/debited to P&L',group:'priorAmtIncCrDrPL'},
  {key:'ProfDeviatDueAcctMeth',path:'PARTA_OI.ProfDeviatDueAcctMeth',label:'Profit deviation due to accounting method',group:'profDeviatDueAcctMeth'},
  {key:'DecProOrIncLossUs145_2',path:'PARTA_OI.DecProOrIncLossUs145_2',label:'Decrease in profit or increase in loss under section 145(2)',group:'decProOrIncLossUs145_2'},
  {key:'NoCredToPLAmt',path:'PARTA_OI.NoCredToPLAmt',label:'Amounts not credited to profit and loss',group:'noCredToPLAmt'},
  {key:'amountOfExpDisallwUs14A',path:'PARTA_OI.AmountOfExpDisAllwUs14A',label:'Section 14A expenditure disallowance',group:'amountOfExpDisallwUs14A'},
  ...entries('noCredToPLAmt','PARTA_OI.NoCredToPLAmt',noCredit),
  ...entries('amountDisallUs36','PARTA_OI.AmtDisallUs36',group36), ...entries('amountDisallUs37','PARTA_OI.AmtDisallUs37',group37),
  ...entries('amountDisallUs40','PARTA_OI.AmtDisallUs40',group40), ...entries('amountDisallUs40A','PARTA_OI.AmtDisallUs40A',group40A),
  ...entries('amountDisallUs43BPrevious','PARTA_OI.AmtDisallUs43BPyNowAll.AmtUs43B',group43B), ...entries('amountDisallUs43B','PARTA_OI.AmtDisall43B.AmtUs43B',group43B),
  ...entries('amountExciseCustomsVATOutstanding','PARTA_OI.AmtExciseCustomsVATOutstanding.ExciseCustomsVAT',excise),
];

export const EMPTY_ITR3_PART_A_OI: ITR3PartAOI = {
  methodOfAcct:'MERC',changeInAcctMethFlg:'N',profDeviatDueAcctMeth:0,decProOrIncLossUs145_2:0,methodOfValClgStk:{},noCredToPLAmt:{},amountDisallUs36:{},amountDisallUs37:{},amountDisallUs40:{},amountDisallUs40A:{},amountDisallUs43BPrevious:{},amountDisallUs43B:{},amountExciseCustomsVATOutstanding:{},deemedProfUs33ABs:0,deemedProfUs33AB:0,deemedProfUs33ABA:0,profTaxAmtUs41:0,priorAmtIncCrDrPL:0,amountOfExpDisallwUs14A:0,interestDisAllowUs23SMEAct:0,scheduleTPSAFlg:'N',otherAdditions:0,otherDeductions:0,
};
export const readItr3PartAOI = (workspace: ITR3BusinessWorkspace): ITR3PartAOI => ({...EMPTY_ITR3_PART_A_OI,...(workspace.core.PARTA_OI as Partial<ITR3PartAOI> | undefined)});
export const updateItr3PartAOI = (workspace: ITR3BusinessWorkspace,key: string,value: unknown): ITR3BusinessWorkspace => {
  const field=ITR3_PART_A_OI_FIELDS.find((item)=>item.key===key); if(!field || computed.has(key)) return workspace;
  const current=readItr3PartAOI(workspace); const next={...current};
  if(field.group==='methodOfAcct') next.methodOfAcct=value==='CASH'?'CASH':'MERC'; else if(field.group==='changeInAcctMethFlg'||field.group==='scheduleTPSAFlg') next[field.group]=value==='Y'?'Y':'N';
  else if(typeof next[field.group]==='object' && next[field.group]!==null) next[field.group]={...(next[field.group] as Record<string, unknown>),[key]:numeric(value)} as never;
  else (next as unknown as Record<string, unknown>)[field.group]=numeric(value);
  return {...workspace,core:{...workspace.core,PARTA_OI:next as unknown as CanonicalJsonValue}};
};
