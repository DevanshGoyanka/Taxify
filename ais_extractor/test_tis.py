"""Test TIS extractor on all 29 PDFs."""
import os, sys, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tis_extractor import extract_tis, tis_to_frontend_json

downloads = r'C:\Users\Devansh\Desktop\Taxify\downloads'

tis_pdfs = []
for root, dirs, files in os.walk(downloads):
    for f in files:
        if 'TIS' in f and f.endswith('.pdf') and '26AS' not in f and f != 'TIS-2025_26.pdf':
            tis_pdfs.append(os.path.join(root, f))

output_dir = os.path.join(os.path.dirname(__file__), 'test_output_tis')
os.makedirs(output_dir, exist_ok=True)

results = []
errors = []

for i, path in enumerate(sorted(tis_pdfs)):
    fname = os.path.basename(path)
    pan = fname[:10]
    try:
        doc = extract_tis(path)
        n_entries = len(doc.entries)
        n_details = sum(len(e.details) for e in doc.entries)
        cats = [e.category for e in doc.entries]

        json_str = tis_to_frontend_json(doc)
        out_path = os.path.join(output_dir, f"{pan}_tis.json")
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(json_str)

        results.append({
            "pan": pan, "name": doc.metadata.name,
            "entries": n_entries, "details": n_details,
            "cats": cats, "file": fname,
        })

        print(f"[{i+1:2d}/{len(tis_pdfs)}] {pan} | {doc.metadata.name} | "
              f"Entries:{n_entries} Details:{n_details} | {cats}")

    except Exception as e:
        errors.append({"file": fname, "error": str(e)})
        import traceback
        traceback.print_exc()
        print(f"[{i+1:2d}/{len(tis_pdfs)}] {fname} | ERROR: {e}")

print(f"\n{'='*80}")
print(f"Success: {len(results)}, Failed: {len(errors)}")

if errors:
    print("\nERRORS:")
    for e in errors:
        print(f"  {e['file']}: {e['error']}")
