"""
Quick 26AS Parser Test
Simple script to test 26AS parsing on a single file or directory.
"""
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app.automation.as26_converter import _parse, PART_META
except ImportError:
    print("ERROR: Cannot find app/automation/as26_converter.py")
    print("Make sure you're running from the Taxify project root directory")
    sys.exit(1)

def test_26as_file(file_path: str):
    """Test parsing a single 26AS file and print results."""
    print(f"Testing: {file_path}")
    print(f"File size: {os.path.getsize(file_path):,} bytes")
    print("-" * 60)
    
    try:
        # Parse the file
        parsed = _parse(file_path)
        
        # Show header info
        header = parsed.get("header", {})
        print("HEADER:")
        for key, value in header.items():
            print(f"  {key}: {value}")
        
        print()
        
        # Show parts summary
        parts = parsed.get("parts", {})
        print(f"PARTS ({len(parts)} total):")
        
        total_deductors = 0
        total_details = 0
        
        for part_key in sorted(parts.keys()):
            part_data = parts[part_key]
            meta = PART_META.get(part_key, {"title": "Unknown", "credit": False})
            
            if part_data.get("empty", True):
                print(f"  {part_key}: {meta['title']} - EMPTY")
            else:
                rows = part_data.get("rows", [])
                deductors = sum(1 for r in rows if r.get("_type") == "deductor")
                details = sum(len(r.get("_details", [])) for r in rows if r.get("_type") == "deductor")
                
                total_deductors += deductors
                total_details += details
                
                print(f"  {part_key}: {meta['title']}")
                print(f"      → {deductors} deductors, {details} detail rows")
        
        print()
        print(f"TOTAL: {total_deductors} deductors, {total_details} detail rows across all parts")
        print("✓ PARSING SUCCESS")
        
    except Exception as e:
        print(f"✗ PARSING FAILED: {e}")
        import traceback
        traceback.print_exc()

def find_26as_files(directory: str) -> list[str]:
    """Find all 26AS TXT files in directory."""
    files = []
    for root, dirs, filenames in os.walk(directory):
        for filename in filenames:
            if ("26as" in filename.lower() or "26AS" in filename) and filename.endswith(".txt"):
                files.append(os.path.join(root, filename))
    return sorted(files)

def main():
    # Default locations to try
    default_locations = [
        r"C:\Users\Devansh\Desktop\E-FILE_karo",
        r"C:\Users\Devansh\Downloads", 
        r"C:\Users\Devansh\Desktop\Taxify\downloads",
        os.path.join(os.path.dirname(__file__), "downloads")
    ]
    
    # Check command line arguments
    if len(sys.argv) > 1:
        target = sys.argv[1]
        if os.path.isfile(target):
            # Test single file
            test_26as_file(target)
            return
        elif os.path.isdir(target):
            # Test all files in directory
            files = find_26as_files(target)
        else:
            print(f"ERROR: {target} is not a valid file or directory")
            return
    else:
        # Try default locations
        files = []
        for location in default_locations:
            if os.path.exists(location):
                found = find_26as_files(location)
                if found:
                    files.extend(found)
                    print(f"Found {len(found)} files in {location}")
    
    if not files:
        print("No 26AS TXT files found!")
        print("Usage:")
        print("  python quick_26as_test.py                    # Auto-find files")
        print("  python quick_26as_test.py file.txt          # Test single file") 
        print("  python quick_26as_test.py /path/to/folder   # Test all files in folder")
        return
    
    print(f"Found {len(files)} 26AS files to test")
    print("=" * 80)
    
    success_count = 0
    for i, file_path in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}] ", end="")
        try:
            test_26as_file(file_path)
            success_count += 1
        except Exception as e:
            print(f"✗ FAILED: {e}")
        
        if i < len(files):
            print("\n" + "="*80)
    
    print(f"\n\nSUMMARY: {success_count}/{len(files)} files parsed successfully")

if __name__ == "__main__":
    main()