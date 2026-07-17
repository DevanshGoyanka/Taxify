// ValidationReportPanel - displays validation results
// Document 3 Phase 3

import React from 'react';
import { ValidationReport, ValidationResult } from '../api/validation';

interface Props {
  report: ValidationReport | null;
  onClose?: () => void;
}

export const ValidationReportPanel: React.FC<Props> = ({ report, onClose }) => {
  if (!report) {
    return null;
  }

  const blockingIssues = report.results.filter(
    r => !r.passed && r.severity === 'BLOCKING'
  );
  const warnings = report.results.filter(
    r => !r.passed && r.severity === 'WARNING'
  );

  return (
    <div className="validation-report-panel">
      <div className="report-header">
        <h3>Validation Report</h3>
        {onClose && <button onClick={onClose}>Close</button>}
      </div>
      
      <div className="report-summary">
        <span className={blockingIssues.length > 0 ? 'error' : 'success'}>
          {blockingIssues.length} Blocking Issues
        </span>
        <span className="warning">
          {warnings.length} Warnings
        </span>
      </div>

      {blockingIssues.length > 0 && (
        <div className="validation-section blocking">
          <h4>Blocking Issues</h4>
          {blockingIssues.map((result, idx) => (
            <ValidationResultItem key={idx} result={result} />
          ))}
        </div>
      )}

      {warnings.length > 0 && (
        <div className="validation-section warnings">
          <h4>Warnings</h4>
          {warnings.map((result, idx) => (
            <ValidationResultItem key={idx} result={result} />
          ))}
        </div>
      )}

      {blockingIssues.length === 0 && warnings.length === 0 && (
        <div className="validation-success">
          All validation checks passed
        </div>
      )}
    </div>
  );
};

const ValidationResultItem: React.FC<{ result: ValidationResult }> = ({ result }) => (
  <div className="validation-result-item">
    <div className="result-validator">{result.validatorName}</div>
    <div className="result-message">{result.message}</div>
    {result.fieldReference && (
      <div className="result-field">Field: {result.fieldReference}</div>
    )}
    {result.itdErrorCode && (
      <div className="result-code">Code: {result.itdErrorCode}</div>
    )}
  </div>
);
