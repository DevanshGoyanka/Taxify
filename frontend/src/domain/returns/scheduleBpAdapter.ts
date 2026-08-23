import type { ITR4ScheduleBPData } from '../../components/business/ITR4ScheduleBPManager';
import { createEmptyFinancialParticulars } from './factory';
import type { ReturnDraft } from './types';

export function scheduleBpFromBusinesses(businesses: ReturnDraft['businesses']): ITR4ScheduleBPData {
  const ad = businesses.filter((row) => row.scheme === '44AD');
  const ada = businesses.filter((row) => row.scheme === '44ADA');
  const ae = businesses.filter((row) => row.scheme === '44AE');
  const fp = businesses[0]?.financialParticulars;
  const gst = businesses.flatMap((row) => row.gstinTurnovers);
  const adIncome = ad.reduce((sum, row) => sum + row.declaredIncome, 0);
  const adaIncome = ada.reduce((sum, row) => sum + row.declaredIncome, 0);
  const aeIncome = ae.reduce((sum, row) => sum + row.declaredIncome, 0);
  return {
    NatOfBus44AD: ad.map((row) => ({ NameOfBusiness: row.businessName, CodeAD: row.natureCode, Description: row.description })),
    PersumptiveInc44AD: ad.length ? {
      GrsTotalTrnOver: ad.reduce((sum, row) => sum + row.digitalReceipts + row.nonDigitalReceipts + row.otherModeReceipts, 0),
      GrsTrnOverBank: ad.reduce((sum, row) => sum + row.digitalReceipts, 0),
      GrsTotalTrnOverInCash: ad.reduce((sum, row) => sum + row.nonDigitalReceipts, 0),
      GrsTrnOverAnyOthMode: ad.reduce((sum, row) => sum + row.otherModeReceipts, 0),
      PersumptiveInc44AD6Per: ad.reduce((sum, row) => sum + row.digitalPresumptiveIncome, 0),
      PersumptiveInc44AD8Per: ad.reduce((sum, row) => sum + row.nonDigitalPresumptiveIncome, 0),
      TotPersumptiveInc44AD: adIncome,
      // Round-trip the "declare higher than minimum" override flags so the
      // ITR4ScheduleBPManager's editable-override state survives the adapter
      // round-trip (businesses -> schedule -> businesses). Without this the
      // flags would be stripped and derive() would re-clamp the user's typed
      // value back to the statutory minimum on every keystroke.
      _override6Per: ad.some((row) => row.declareHigher6Per),
      _override8Per: ad.some((row) => row.declareHigher8Per),
    } : undefined,
    NatOfBus44ADA: ada.map((row) => ({ NameOfBusiness: row.businessName, CodeADA: row.natureCode, Description: row.description })),
    PersumptiveInc44ADA: ada.length ? {
      GrsReceipt: ada.reduce((sum, row) => sum + row.grossReceipts, 0),
      GrsTrnOverBank44ADA: ada.reduce((sum, row) => sum + row.digitalReceipts, 0),
      GrsTotalTrnOverInCash44ADA: ada.reduce((sum, row) => sum + row.nonDigitalReceipts, 0),
      GrsTrnOverAnyOthMode44ADA: ada.reduce((sum, row) => sum + row.otherModeReceipts, 0),
      TotPersumptiveInc44ADA: adaIncome,
    } : undefined,
    NatOfBus44AE: ae.map((row) => ({ NameOfBusiness: row.businessName, CodeAE: row.natureCode, Description: row.description })),
    GoodsDtlsUs44AE: ae.flatMap((row) => row.vehicles.map((vehicle) => ({
      RegNumberGoodsCarriage: vehicle.vehicleNumber,
      OwnedLeasedHiredFlag: vehicle.ownedLeasedHiredFlag,
      TonnageCapacity: vehicle.tonnage,
      HoldingPeriod: vehicle.ownedMonths,
      PresumptiveIncome: vehicle.presumptiveIncome,
    }))),
    PersumptiveInc44AE: ae.length ? {
      TotPersumInc44AE: ae.reduce((sum, row) => sum + row.declaredIncome + row.salaryInterestFromFirm, 0),
      SalInterestByFirm: ae.reduce((sum, row) => sum + row.salaryInterestFromFirm, 0),
      TotalPersumptiveInc: aeIncome,
      IncChargeableUnderBus: adIncome + adaIncome + aeIncome,
    } : undefined,
    TurnoverGrsRcptForGSTIN: gst.map((row) => ({ GSTINNo: row.gstin, AmtTurnGrossRcptGSTIN: row.turnover })),
    TotalTurnoverGrsRcptGSTIN: gst.reduce((sum, row) => sum + row.turnover, 0),
    FinanclPartclrOfBusiness: fp ? {
      PartnerMemberOwnCapital: fp.partnerMemberOwnCapital, SecuredLoans: fp.securedLoans,
      UnSecuredLoans: fp.unsecuredLoans, Advances: fp.advances, SundryCreditors: fp.sundryCreditors,
      OthrCurrLiab: fp.otherLiabilities, TotCapLiabilities: fp.totalLiabilities,
      FixedAssets: fp.fixedAssets, Investments: fp.investments, Inventories: fp.inventory,
      SundryDebtors: fp.sundryDebtors, BalWithBanks: fp.bankBalance, CashInHand: fp.cashBalance,
      LoansAndAdvances: fp.loansAndAdvances, OtherAssets: fp.otherAssets, TotalAssets: fp.totalAssets,
    } : undefined,
  };
}

export function businessesFromScheduleBp(data: ITR4ScheduleBPData): ReturnDraft['businesses'] {
  const fpData = data.FinanclPartclrOfBusiness ?? {};
  const financialParticulars = {
    ...createEmptyFinancialParticulars(),
    partnerMemberOwnCapital: fpData.PartnerMemberOwnCapital ?? 0,
    securedLoans: fpData.SecuredLoans ?? 0, unsecuredLoans: fpData.UnSecuredLoans ?? 0,
    advances: fpData.Advances ?? 0, sundryCreditors: fpData.SundryCreditors ?? 0,
    otherLiabilities: fpData.OthrCurrLiab ?? 0, totalLiabilities: fpData.TotCapLiabilities ?? 0,
    fixedAssets: fpData.FixedAssets ?? 0, investments: fpData.Investments ?? 0,
    inventory: fpData.Inventories ?? 0, sundryDebtors: fpData.SundryDebtors ?? 0,
    bankBalance: fpData.BalWithBanks ?? 0, cashBalance: fpData.CashInHand ?? 0,
    loansAndAdvances: fpData.LoansAndAdvances ?? 0, otherAssets: fpData.OtherAssets ?? 0,
    totalAssets: fpData.TotalAssets ?? 0,
  };
  const gstinTurnovers = (data.TurnoverGrsRcptForGSTIN ?? []).map((row, index) => ({
    id: `schedule-bp-gstin-${index}`, gstin: row.GSTINNo, turnover: row.AmtTurnGrossRcptGSTIN,
  }));
  const rows: ReturnDraft['businesses'] = [];
  (data.NatOfBus44AD ?? []).forEach((nature, index) => {
    const values = data.PersumptiveInc44AD;
    rows.push({
      id: `schedule-bp-44ad-${index}`, scheme: '44AD', businessName: nature.NameOfBusiness,
      natureCode: nature.CodeAD, description: nature.Description ?? '',
      digitalReceipts: index === 0 ? values?.GrsTrnOverBank ?? 0 : 0,
      nonDigitalReceipts: index === 0 ? values?.GrsTotalTrnOverInCash ?? 0 : 0,
      otherModeReceipts: index === 0 ? values?.GrsTrnOverAnyOthMode ?? 0 : 0,
      digitalPresumptiveIncome: index === 0 ? values?.PersumptiveInc44AD6Per ?? 0 : 0,
      nonDigitalPresumptiveIncome: index === 0 ? values?.PersumptiveInc44AD8Per ?? 0 : 0,
      declaredIncome: index === 0 ? values?.TotPersumptiveInc44AD ?? 0 : 0,
      // Preserve the override flags (local-only, never serialized to the
      // official CBDT JSON because the JSON builder reads only official keys).
      declareHigher6Per: index === 0 ? Boolean((values as { _override6Per?: boolean } | undefined)?._override6Per) : false,
      declareHigher8Per: index === 0 ? Boolean((values as { _override8Per?: boolean } | undefined)?._override8Per) : false,
      gstinTurnovers: index === 0 ? gstinTurnovers : [], financialParticulars,
    });
  });
  (data.NatOfBus44ADA ?? []).forEach((nature, index) => {
    const values = data.PersumptiveInc44ADA;
    rows.push({
      id: `schedule-bp-44ada-${index}`, scheme: '44ADA', businessName: nature.NameOfBusiness,
      natureCode: nature.CodeADA, description: nature.Description ?? '',
      grossReceipts: index === 0 ? values?.GrsReceipt ?? 0 : 0,
      digitalReceipts: index === 0 ? values?.GrsTrnOverBank44ADA ?? 0 : 0,
      nonDigitalReceipts: index === 0 ? values?.GrsTotalTrnOverInCash44ADA ?? 0 : 0,
      otherModeReceipts: index === 0 ? values?.GrsTrnOverAnyOthMode44ADA ?? 0 : 0,
      declaredIncome: index === 0 ? values?.TotPersumptiveInc44ADA ?? 0 : 0,
      gstinTurnovers: rows.length === 0 && index === 0 ? gstinTurnovers : [], financialParticulars,
    });
  });
  (data.NatOfBus44AE ?? []).forEach((nature, index) => {
    rows.push({
      id: `schedule-bp-44ae-${index}`, scheme: '44AE', businessName: nature.NameOfBusiness,
      natureCode: nature.CodeAE, description: nature.Description ?? '',
      vehicles: index === 0 ? (data.GoodsDtlsUs44AE ?? []).map((vehicle, vehicleIndex) => ({
        id: `schedule-bp-vehicle-${vehicleIndex}`, vehicleNumber: vehicle.RegNumberGoodsCarriage,
        vehicleType: vehicle.TonnageCapacity > 12 ? 'HEAVY' : 'OTHER',
        tonnage: vehicle.TonnageCapacity, ownedMonths: vehicle.HoldingPeriod,
        leasedOrHired: vehicle.OwnedLeasedHiredFlag !== 'OWN',
        ownedLeasedHiredFlag: vehicle.OwnedLeasedHiredFlag,
        presumptiveIncome: vehicle.PresumptiveIncome,
      })) : [],
      declaredIncome: index === 0 ? data.PersumptiveInc44AE?.TotalPersumptiveInc ?? 0 : 0,
      salaryInterestFromFirm: index === 0 ? data.PersumptiveInc44AE?.SalInterestByFirm ?? 0 : 0,
      gstinTurnovers: rows.length === 0 && index === 0 ? gstinTurnovers : [], financialParticulars,
    });
  });
  if (rows.length > 0 && !rows.some((row) => row.gstinTurnovers.length > 0)) {
    rows[0] = { ...rows[0], gstinTurnovers };
  }
  return rows;
}
