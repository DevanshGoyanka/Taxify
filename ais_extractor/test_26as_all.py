"""Test 26AS extractor on all 30 PDFs and save output JSONs."""
import os, sys, json

sys.path.insert(0, r'C:\Users\Devansh\Desktop\Taxify\ais_extractor')
from as26_extractor import extract_26as

downloads = r'C:\Users\Devansh\Desktop\Taxify\downloads'

pdfs = []
for root, dirs, files in os.walk(downloads):
    for f in files:
        if '26AS' in f and f.endswith('.pdf') and '26AS' in f:
            pdfs.append(os.path.join(root, f))

output_dir = os.path.join(os.path.dirname(__file__), 'test_output_26as')
os.makedirs(output_dir, exist_ok=True)

results = []
errors = []

for i, path in enumerate(pdfs, 1):
    fname = os.path.basename(path)
    try:
        result = extract_26as(path)
        # Count summary and detail rows in parts with data
        data_parts = []
        total_sum = 0
        total_det = 0
        for pid, part in result["parts"].items():
            if not part.get("empty", True):
                total_sum += len(part.get("rows", []))
                total_det += sum(len(r.get("_details", [])) for r in part.get("rows", []))
                data_parts.append(f"{pid}({len(part['rows'])}/{sum(len(r.get('_details',[])) for r in part['rows'])})")

        # Save JSON
        pan = result["header"].get("Permanent Account Number (PAN)", "UNKNOWN")
        out_name = f"{pan}_{fname.replace('.pdf','')}.json"
        out_path = os.path.join(output_dir, out_name)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        status = "OK"
        name = result["header"].get("Name of Assessee", "UNKNOWN")
        parts_str = " ".join(data_parts) if data_parts else "all_empty"
        print(f"[{i:2d}/{len(pdfs)}] {pan} | {name[:30]} | {parts_str} | {status}")
        results.append({"pan": pan, "name": name, "data_parts": data_parts, "status": status})

    except Exception as e:
        print(f"[{i:2d}/{len(pdfs)}] {fname} | ERROR: {e}")
        errors.append({"file": fname, "error": str(e)})

print(f"\n=== SUMMARY ===")
print(f"Success: {len(results)}, Errors: {len(errors)}")
data_count = sum(1 for r in results if r["data_parts"])
empty_count = sum(1 for r in results if not r["data_parts"])
print(f"With data: {data_count}, All empty: {empty_count}")

if errors:
    print("\nERRORS:")
    for e in errors:
        print(f"  {e['file']}: {e['error']}")
