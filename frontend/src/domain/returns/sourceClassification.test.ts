import { describe, expect, it } from 'vitest';
import { AIS_CLASSIFICATIONS, AS26_CLASSIFICATIONS, TIS_CLASSIFICATIONS, classifySource, deterministicEvidenceId } from './sourceClassification';

const REQUIRED_AIS_CODES = ['TDS-192','TDS-ANN.II-SAL','TDS-194','TDS-194A','TDS-194BA','TDS-194C','TDS-194D','TDS-194H','TDS-194K','TDS-194N','TDS-194NF','TDS-194R','TDS-194S','TDS-194T','TDS-194IA(R)','TDS-194IA(RV)','SFT-015','SFT-18(Div)','SFT-016(SB)','SFT-016(TD)','SFT-016(RD)','SFT-003(P)','SFT-003(R)','SFT-004(P)','SFT-004(R)','SFT-005','SFT-006','SFT-17-LES(M)','SFT-17(Pur)','SFT-18-EMF(M)','SFT-18-OTU(M)','SFT-18(Pur)','SFT-012','SFT-012(P)','EXC-GSTR3B','EXC-GSTR1(P)'];
const REQUIRED_TIS = ['salary','dividend','interest from savings bank','interest from deposit','business receipts','insurance commission','gst turnover','gst purchases','cash deposits','cash withdrawals','miscellaneous payment','outward foreign remittance/purchase of foreign currency','purchase of immovable property','purchase of securities and units of mutual funds','purchase of time deposits','purchase of vehicle','receipt of amount by partners from partnership firm','receipts from transfer of immovable property','receipts on transfer of virtual digital asset','sale of land or building','sale of securities and units of mutual fund','winnings from online games'];
const REQUIRED_26AS = ['192','192A','193','194','194A','194B','194BA','194BB','194C','194D','194H','194I','194IA','194IB','194J','194K','194M','194N','194NF','194O','194Q','194R','194S','194T','206C','206CE','206CF'];

describe('source classification registry coverage', () => {
  it('classifies every required AIS code with no unknowns', () => {
    for (const code of REQUIRED_AIS_CODES) {
      const classification = AIS_CLASSIFICATIONS[code.toUpperCase()];
      expect(classification, `AIS code ${code} must be registered`).toBeDefined();
      expect(classification.role).not.toBe('PARSER_WARNING');
    }
  });

  it('classifies every required TIS category with no unknowns', () => {
    for (const category of REQUIRED_TIS) {
      const classification = TIS_CLASSIFICATIONS[category.toLowerCase()];
      expect(classification, `TIS category ${category} must be registered`).toBeDefined();
      expect(classification.role).not.toBe('PARSER_WARNING');
    }
  });

  it('classifies every required 26AS section with no unknowns', () => {
    for (const section of REQUIRED_26AS) {
      const classification = AS26_CLASSIFICATIONS[section];
      expect(classification, `26AS section ${section} must be registered`).toBeDefined();
      expect(classification.role).not.toBe('PARSER_WARNING');
    }
  });

  it('maps unknown codes to PARSER_WARNING requiring review', () => {
    expect(classifySource('AIS', 'TDS-999').role).toBe('PARSER_WARNING');
    expect(classifySource('AIS', 'TDS-999').relatedTab).toBe('RECONCILIATION');
    expect(classifySource('TIS', 'mystery category').role).toBe('PARSER_WARNING');
    expect(classifySource('26AS', '999').role).toBe('PARSER_WARNING');
    expect(classifySource('AIS', '').role).toBe('PARSER_WARNING');
  });

  it('produces deterministic evidence ids', () => {
    const a = deterministicEvidenceId('AIS', 'TDS-192', 'ABC');
    const b = deterministicEvidenceId('AIS', 'TDS-192', 'ABC');
    const c = deterministicEvidenceId('AIS', 'TDS-192', 'DEF');
    expect(a).toBe(b);
    expect(a).not.toBe(c);
    expect(a.startsWith('evidence-ais-')).toBe(true);
  });
});
