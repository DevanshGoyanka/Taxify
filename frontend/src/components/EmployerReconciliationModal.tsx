

interface FieldDiscrepancy {
  fieldName: string;
  existingValue: number;
  newValue: number;
  difference: number;
  description: string;
  suggestion: string;
}

interface EmployerDiscrepancy {
  employerName: string;
  employerTAN: string;
  importSource: string;
  fieldDiscrepancies: FieldDiscrepancy[];
  summary: string;
  recommendation: string;
}

interface EmployerReconciliationResult {
  importSource: string;
  mergedEntries: any[];
  discrepancies: EmployerDiscrepancy[];
  warnings: string[];
  newEntries: string[];
  skippedDuplicates: string[];
  discrepancyCount: number;
  summary: string;
}

interface EmployerReconciliationModalProps {
  show: boolean;
  result: EmployerReconciliationResult | null;
  onClose: () => void;
  onResolve: (discrepancy: EmployerDiscrepancy, action: 'KEEP_EXISTING' | 'USE_NEW' | 'MANUAL') => void;
}

export default function EmployerReconciliationModal({ 
  show, 
  result, 
  onClose, 
  onResolve 
}: EmployerReconciliationModalProps) {
  if (!show || !result) return null;

  const hasDiscrepancies = result.discrepancies && result.discrepancies.length > 0;
  const hasNewEntries = result.newEntries && result.newEntries.length > 0;
  const hasSkipped = result.skippedDuplicates && result.skippedDuplicates.length > 0;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-7xl w-full max-h-[90vh] overflow-hidden">
        <div className="p-6 border-b bg-gradient-to-r from-blue-50 to-indigo-50">
          <h2 className="text-2xl font-bold text-gray-800">Employer Import Reconciliation</h2>
          <p className="text-gray-600 mt-2">{result.summary}</p>
        </div>

        <div className="p-6 overflow-y-auto max-h-[65vh]">
          {/* New Entries Section */}
          {hasNewEntries && (
            <div className="mb-6">
              <h3 className="text-lg font-semibold text-green-700 mb-3">
                ✓ New Employers Added ({result.newEntries.length})
              </h3>
              <div className="bg-green-50 border border-green-200 rounded p-4">
                <ul className="list-disc list-inside space-y-1">
                  {result.newEntries.map((entry, idx) => (
                    <li key={idx} className="text-green-800">{entry}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Skipped Duplicates Section */}
          {hasSkipped && (
            <div className="mb-6">
              <h3 className="text-lg font-semibold text-blue-700 mb-3">
                ⊘ Duplicate Employers Skipped ({result.skippedDuplicates.length})
              </h3>
              <div className="bg-blue-50 border border-blue-200 rounded p-4">
                <ul className="list-disc list-inside space-y-1">
                  {result.skippedDuplicates.map((entry, idx) => (
                    <li key={idx} className="text-blue-800">{entry}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Discrepancies Section */}
          {hasDiscrepancies && (
            <div className="mb-6">
              <h3 className="text-lg font-semibold text-orange-700 mb-3">
                ⚠ Discrepancies Found ({result.discrepancies.length})
              </h3>
              <p className="text-sm text-gray-600 mb-4">
                The following employers exist in your form but have different values in the imported document. 
                Review and choose which values to keep.
              </p>

              {result.discrepancies.map((discrepancy, idx) => (
                <div key={idx} className="mb-6 border border-orange-200 rounded-lg overflow-hidden">
                  <div className="bg-orange-50 p-4 border-b border-orange-200">
                    <h4 className="font-semibold text-gray-800">
                      {discrepancy.employerName} <span className="text-sm font-mono text-gray-600">(TAN: {discrepancy.employerTAN})</span>
                    </h4>
                    <p className="text-sm text-gray-600 mt-1">{discrepancy.summary}</p>
                  </div>

                  <div className="p-4">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-gray-100">
                          <th className="border p-2 text-left">Field</th>
                          <th className="border p-2 text-right">Existing Value</th>
                          <th className="border p-2 text-right">New Value ({result.importSource})</th>
                          <th className="border p-2 text-right">Difference</th>
                          <th className="border p-2 text-left">Suggestion</th>
                        </tr>
                      </thead>
                      <tbody>
                        {discrepancy.fieldDiscrepancies.map((field, fieldIdx) => (
                          <tr key={fieldIdx} className="hover:bg-gray-50">
                            <td className="border p-2 font-medium">{field.fieldName}</td>
                            <td className="border p-2 text-right font-mono">₹{field.existingValue.toLocaleString('en-IN')}</td>
                            <td className="border p-2 text-right font-mono text-blue-600">₹{field.newValue.toLocaleString('en-IN')}</td>
                            <td className="border p-2 text-right font-mono text-orange-600">₹{field.difference.toLocaleString('en-IN')}</td>
                            <td className="border p-2 text-xs text-gray-600">{field.suggestion}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>

                    <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded">
                      <p className="text-sm text-blue-800">
                        <strong>Recommendation:</strong> {discrepancy.recommendation}
                      </p>
                    </div>

                    <div className="mt-4 flex gap-3 justify-end">
                      <button
                        onClick={() => onResolve(discrepancy, 'KEEP_EXISTING')}
                        className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 text-sm"
                      >
                        Keep Existing Values
                      </button>
                      <button
                        onClick={() => onResolve(discrepancy, 'USE_NEW')}
                        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
                      >
                        Use New Values from {result.importSource}
                      </button>
                      <button
                        onClick={() => onResolve(discrepancy, 'MANUAL')}
                        className="px-4 py-2 bg-orange-600 text-white rounded hover:bg-orange-700 text-sm"
                      >
                        Review Manually
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Warnings Section */}
          {result.warnings && result.warnings.length > 0 && (
            <div className="mb-6">
              <h3 className="text-lg font-semibold text-yellow-700 mb-3">
                ⚠ Warnings
              </h3>
              <div className="bg-yellow-50 border border-yellow-200 rounded p-4">
                <ul className="list-disc list-inside space-y-1">
                  {result.warnings.map((warning, idx) => (
                    <li key={idx} className="text-yellow-800">{warning}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* No Issues Section */}
          {!hasDiscrepancies && !hasNewEntries && !hasSkipped && (
            <div className="text-center py-8">
              <div className="text-6xl mb-4">✓</div>
              <h3 className="text-xl font-semibold text-green-700">All Clear!</h3>
              <p className="text-gray-600 mt-2">No discrepancies or duplicates found.</p>
            </div>
          )}
        </div>

        <div className="p-6 border-t bg-gray-50 flex justify-between items-center">
          <div className="text-sm text-gray-600">
            {hasDiscrepancies && (
              <span className="text-orange-600 font-semibold">
                Action required for {result.discrepancies.length} employer(s)
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            className="px-6 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 font-medium"
          >
            {hasDiscrepancies ? 'Review Later' : 'Close'}
          </button>
        </div>
      </div>
    </div>
  );
}
