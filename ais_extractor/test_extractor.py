"""Full test of extractor v2 on all 29 AIS PDFs."""
import os, sys, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extractor import extract_ais, ais_to_frontend_json

downloads = r'C:\Users\Devansh\Desktop\Taxify\downloads'

ais_pdfs = []
for root, dirs, files in os.walk(downloads):
    for f in files:
        if 'AIS' in f and f.endswith('.pdf') and not f.startswith('TIS'):
            ais_pdfs.append(os.path.join(root, f))

output_dir = os.path.join(os.path.dirname(__file__), 'test_output')
os.makedirs(output_dir, exist_ok=True)

results = []
errors = []

for i, path in enumerate(sorted(ais_pdfs)):
    fname = os.path.basename(path)
    pan = fname[:10]
    try:
        doc = extract_ais(path)
        b1_c = len(doc.b1_entries)
        b2_c = len(doc.b2_entries)
        b7_c = len(doc.b7_entries)
        total_details = sum(len(e.details) for e in doc.b1_entries) + \
                        sum(len(e.details) for e in doc.b2_entries) + \
                        sum(len(e.details) for e in doc.b7_entries)
        tax = len(doc.tax_payments)
        refund = len(doc.refunds)
        heads = list(doc.income_head_groups.keys())

        json_str = ais_to_frontend_json(doc)
        out_path = os.path.join(output_dir, f"{pan}_ais.json")
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(json_str)

        results.append({
            "pan": pan, "name": doc.metadata.name, "fy": doc.metadata.financial_year,
            "b1": b1_c, "b2": b2_c, "b7": b7_c,
            "details": total_details, "tax": tax, "refund": refund,
            "heads": heads, "file": fname,
        })

        print(f"[{i+1:2d}/{len(ais_pdfs)}] {pan} | {doc.metadata.name} | "
              f"B1:{b1_c} B2:{b2_c} B7:{b7_c} D:{total_details} T:{tax} R:{refund} | {heads}")

    except Exception as e:
        errors.append({"file": fname, "error": str(e)})
        print(f"[{i+1:2d}/{len(ais_pdfs)}] {fname} | ERROR: {e}")

print(f"\n{'='*80}")
print(f"Success: {len(results)}, Failed: {len(errors)}")

if errors:
    print("\nERRORS:")
    for e in errors:
        print(f"  {e['file']}: {e['error']}")

aggregate = {
    "total_processed": len(results),
    "total_failed": len(errors),
    "results": results,
    "errors": errors,
}
with open(os.path.join(output_dir, "_aggregate_results.json"), 'w', encoding='utf-8') as f:
    json.dump(aggregate, f, indent=2, ensure_ascii=False)
