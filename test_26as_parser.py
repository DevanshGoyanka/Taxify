"""
26AS Parser Test Script
Parses 26AS TXT file and prints all extracted data.
"""
import os
import sys
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.automation.as26_converter import _parse, PART_META, STATUS_FULL

def format_header(header: dict) -> str:
    """Format header fields for display."""
    lines = ["=" * 60, "HEADER INFORMATION", "=" * 60]
    for key, value in header.items():
        lines.append(f"  {key}: {value}")
    return "\n".join(lines)

def format_part(part_key: str, part_data: dict) -> str:
    """Format a single part (I, II, III, etc.) for display."""
    meta = PART_META.get(part_key, {"title": "Unknown", "credit": False})
    title = meta.get("title", "Unknown")
    is_credit = meta.get("credit", False)
    
    lines = [f"\n{'=' * 60}"]
    lines.append(f"PART {part_key}: {title}")
    lines.append(f"Type: {'Credit' if is_credit else 'Demand'}")
    lines.append(f"{'=' * 60}")
    
    if part_data.get("empty", True):
        lines.append("  (No data)")
        return "\n".join(lines)
    
    rows = part_data.get("rows", [])
    if not rows:
        lines.append("  (No rows)")
        return "\n".join(lines)
    
    # Print each row
    lines.append(f"Total rows: {len(rows)}")
    lines.append("-" * 60)
    
    for idx, row in enumerate(rows, 1):
        lines.append(f"\n  Row {idx}:")
        # Sort keys for consistent display
        for field, value in sorted(row.items()):
            if value and str(value).strip():
                lines.append(f"    {field}: {value}")
    
    return "\n".join(lines)

def main():
    # Path to 26AS TXT file
    txt_path = r"C:\Users\Devansh\Downloads\EPPPG3078Q-DEVANSH SUNIT GOYANKA\AY_2026_27\EPPPG3078Q-26AS-2026_27.txt"
    
    # Check if file exists
    if not os.path.exists(txt_path):
        print(f"ERROR: 26AS TXT file not found at: {txt_path}")
        
        # Try alternative paths
        alt_paths = [
            r"C:\Users\Devansh\Desktop\Taxify\downloads\EPPPG3078Q-26AS-2026_27.txt",
            r"C:\Users\Devansh\Desktop\Taxify\downloads\26AS\EPPPG3078Q-26AS-2026_27.txt",
        ]
        
        for alt in alt_paths:
            if os.path.exists(alt):
                txt_path = alt
                print(f"Found at alternative path: {txt_path}")
                break
        else:
            sys.exit(1)
    
    print(f"Parsing 26AS file: {txt_path}")
    print(f"File size: {os.path.getsize(txt_path):,} bytes")
    print()
    
    # Parse the file
    parsed_data = _parse(txt_path)
    
    # Print header
    header = parsed_data.get("header", {})
    print(format_header(header))
    
    # Print all parts
    parts = parsed_data.get("parts", {})
    print(f"\n\n{'#' * 60}")
    print(f"# PARTS DATA (Total Parts: {len(parts)})")
    print(f"{'#' * 60}")
    
    # Print parts in order (I, II, III, etc.)
    part_order = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X_A", "X_B", "XI"]
    for part_key in part_order:
        if part_key in parts:
            print(format_part(part_key, parts[part_key]))
    
    # Print any additional parts not in standard order
    for part_key in sorted(parts.keys()):
        if part_key not in part_order:
            print(format_part(part_key, parts[part_key]))
    
    # Summary
    print(f"\n\n{'#' * 60}")
    print(f"# PARSING COMPLETE")
    print(f"{'#' * 60}")
    print(f"Total parts with data: {sum(1 for p in parts.values() if not p.get('empty', True))}")
    print(f"Total parts: {len(parts)}")
    
    # Also save JSON output for programmatic use
    json_path = txt_path.replace(".txt", "_parsed.json")
    
    # Convert sets to lists for JSON serialization
    json_data = {
        "header": header,
        "parts": {
            k: {
                "rows": v.get("rows", []), 
                "empty": v.get("empty", True)
            } for k, v in parts.items()
        }
    }
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    
    print(f"\nJSON output saved to: {json_path}")

if __name__ == "__main__":
    main()