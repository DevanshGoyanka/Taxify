"""
26AS Batch Parser Test Script
Scans directory structure for 26AS TXT files and tests parsing on all of them.
Generates comprehensive reports on parsing success/failure and data extraction.
"""
import os
import sys
import json
import traceback
from pathlib import Path
from datetime import datetime
import glob

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app.automation.as26_converter import _parse, PART_META, STATUS_FULL
except ImportError:
    print("ERROR: Could not import 26AS converter. Make sure app/automation/as26_converter.py exists.")
    sys.exit(1)

class TestResult:
    def __init__(self):
        self.total_files = 0
        self.successful_parses = 0
        self.failed_parses = 0
        self.results = []
        self.errors = []

def scan_for_26as_files(root_dir: str) -> list[str]:
    """Recursively scan directory for 26AS TXT files."""
    patterns = [
        "**/*26AS*.txt",
        "**/26AS*.txt", 
        "**/*26as*.txt",
        "**/26as*.txt",
        "**/*-26AS-*.txt",
        "**/*_26AS_*.txt"
    ]
    
    files = set()
    root_path = Path(root_dir)
    
    for pattern in patterns:
        try:
            found = list(root_path.glob(pattern))
            files.update(str(f) for f in found)
        except Exception as e:
            print(f"Warning: Error scanning with pattern {pattern}: {e}")
    
    return sorted(list(files))

def extract_client_info(file_path: str) -> dict:
    """Extract client information from file path and name."""
    path = Path(file_path)
    
    # Extract PAN from filename (assuming format like ABCDE1234F-26AS-2026_27.txt)
    filename = path.name
    pan = None
    
    # Try various PAN patterns
    import re
    pan_patterns = [
        r'([A-Z]{5}[0-9]{4}[A-Z]{1})',  # Standard PAN format
        r'^([A-Z0-9]{10})-',            # PAN at start of filename
    ]
    
    for pattern in pan_patterns:
        match = re.search(pattern, filename)
        if match:
            pan = match.group(1)
            break
    
    # Extract client name from directory structure
    client_name = None
    parts = path.parts
    for part in parts:
        if '-' in part and len(part) > 15:  # Likely contains PAN-NAME format
            if pan and pan in part:
                client_name = part.replace(pan, '').strip('-').strip()
                break
    
    # Extract assessment year
    ay_match = re.search(r'(20\d{2}[-_]?\d{2})', filename)
    assessment_year = ay_match.group(1) if ay_match else "Unknown"
    
    return {
        "pan": pan or "Unknown",
        "client_name": client_name or "Unknown", 
        "assessment_year": assessment_year,
        "file_size": path.stat().st_size if path.exists() else 0,
        "relative_path": str(path.relative_to(Path(file_path).anchor)) if path.is_absolute() else str(path)
    }

def test_single_file(file_path: str, test_result: TestResult) -> dict:
    """Test parsing a single 26AS file."""
    result = {
        "file_path": file_path,
        "client_info": extract_client_info(file_path),
        "success": False,
        "error": None,
        "parsing_stats": {},
        "data_summary": {}
    }
    
    try:
        # Attempt parsing
        parsed_data = _parse(file_path)
        
        # Extract statistics
        header = parsed_data.get("header", {})
        parts = parsed_data.get("parts", {})
        
        # Count parts with data
        parts_with_data = sum(1 for p in parts.values() if not p.get("empty", True))
        total_parts = len(parts)
        
        # Count total rows across all parts
        total_rows = 0
        total_deductors = 0
        total_details = 0
        
        for part_key, part_data in parts.items():
            if not part_data.get("empty", True):
                rows = part_data.get("rows", [])
                total_rows += len(rows)
                
                for row in rows:
                    if row.get("_type") == "deductor":
                        total_deductors += 1
                        total_details += len(row.get("_details", []))
        
        result["success"] = True
        result["parsing_stats"] = {
            "header_fields": len(header),
            "total_parts": total_parts,
            "parts_with_data": parts_with_data,
            "total_rows": total_rows,
            "total_deductors": total_deductors,
            "total_detail_rows": total_details
        }
        
        result["data_summary"] = {
            "header_keys": list(header.keys()),
            "parts_present": list(parts.keys()),
            "parts_with_data": [k for k, v in parts.items() if not v.get("empty", True)],
            "sample_header": dict(list(header.items())[:5])  # First 5 header fields
        }
        
        test_result.successful_parses += 1
        
    except Exception as e:
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()
        test_result.failed_parses += 1
        test_result.errors.append({
            "file": file_path,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
    
    test_result.total_files += 1
    test_result.results.append(result)
    return result

def generate_report(test_result: TestResult, output_dir: str):
    """Generate comprehensive test report."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Summary report
    summary_path = os.path.join(output_dir, f"26as_test_summary_{timestamp}.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("26AS BATCH PARSER TEST REPORT\n")
        f.write("=" * 80 + "\n")
        f.write(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Files Tested: {test_result.total_files}\n")
        f.write(f"Successful Parses: {test_result.successful_parses}\n")
        f.write(f"Failed Parses: {test_result.failed_parses}\n")
        f.write(f"Success Rate: {(test_result.successful_parses/test_result.total_files*100):.1f}%\n" if test_result.total_files > 0 else "Success Rate: N/A\n")
        f.write("\n")
        
        # Success details
        f.write("SUCCESSFUL PARSES:\n")
        f.write("-" * 50 + "\n")
        for result in test_result.results:
            if result["success"]:
                client = result["client_info"]
                stats = result["parsing_stats"]
                f.write(f"✓ {client['pan']} - {client['client_name']} (AY: {client['assessment_year']})\n")
                f.write(f"  File: {os.path.basename(result['file_path'])}\n")
                f.write(f"  Stats: {stats['parts_with_data']}/{stats['total_parts']} parts, ")
                f.write(f"{stats['total_deductors']} deductors, {stats['total_detail_rows']} details\n")
                f.write(f"  Parts: {', '.join(result['data_summary']['parts_with_data'])}\n\n")
        
        # Error details
        if test_result.errors:
            f.write("\nERRORS:\n")
            f.write("-" * 50 + "\n")
            for error in test_result.errors:
                f.write(f"✗ {os.path.basename(error['file'])}\n")
                f.write(f"  Error: {error['error']}\n\n")
    
    # Detailed JSON report
    json_path = os.path.join(output_dir, f"26as_test_detailed_{timestamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "total_files": test_result.total_files,
                "successful_parses": test_result.successful_parses,
                "failed_parses": test_result.failed_parses,
                "success_rate": test_result.successful_parses/test_result.total_files if test_result.total_files > 0 else 0,
                "test_timestamp": datetime.now().isoformat()
            },
            "results": test_result.results,
            "errors": test_result.errors
        }, f, indent=2, ensure_ascii=False)
    
    print(f"Summary report saved to: {summary_path}")
    print(f"Detailed JSON report saved to: {json_path}")

def main():
    # Configuration
    search_dir = r"C:\Users\Devansh\Desktop\E-FILE_karo"
    output_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Allow command line override
    if len(sys.argv) > 1:
        search_dir = sys.argv[1]
    if len(sys.argv) > 2:
        output_dir = sys.argv[2]
    
    print(f"26AS Batch Parser Test")
    print(f"Search Directory: {search_dir}")
    print(f"Output Directory: {output_dir}")
    print("=" * 60)
    
    # Check if search directory exists
    if not os.path.exists(search_dir):
        print(f"ERROR: Search directory does not exist: {search_dir}")
        print("\nTrying alternative locations...")
        
        # Try some common alternative locations
        alternatives = [
            r"C:\Users\Devansh\Downloads",
            r"C:\Users\Devansh\Desktop",
            os.path.join(os.path.dirname(__file__), "downloads"),
            os.path.dirname(__file__)
        ]
        
        found_dir = None
        for alt_dir in alternatives:
            if os.path.exists(alt_dir):
                # Check if it contains any 26AS files
                test_files = scan_for_26as_files(alt_dir)
                if test_files:
                    found_dir = alt_dir
                    print(f"Found {len(test_files)} 26AS files in: {alt_dir}")
                    break
        
        if found_dir:
            search_dir = found_dir
        else:
            print("No 26AS files found in any location. Exiting.")
            return
    
    # Scan for 26AS files
    print("Scanning for 26AS TXT files...")
    txt_files = scan_for_26as_files(search_dir)
    
    if not txt_files:
        print(f"No 26AS TXT files found in {search_dir}")
        return
    
    print(f"Found {len(txt_files)} 26AS TXT files")
    print()
    
    # Initialize test result tracker
    test_result = TestResult()
    
    # Test each file
    for i, file_path in enumerate(txt_files, 1):
        print(f"Testing {i}/{len(txt_files)}: {os.path.basename(file_path)}")
        
        result = test_single_file(file_path, test_result)
        
        if result["success"]:
            stats = result["parsing_stats"]
            print(f"  ✓ Success - {stats['parts_with_data']} parts, {stats['total_deductors']} deductors")
        else:
            print(f"  ✗ Failed - {result['error']}")
    
    print()
    print("=" * 60)
    print("BATCH TEST COMPLETE")
    print("=" * 60)
    print(f"Total Files: {test_result.total_files}")
    print(f"Successful: {test_result.successful_parses}")
    print(f"Failed: {test_result.failed_parses}")
    if test_result.total_files > 0:
        print(f"Success Rate: {(test_result.successful_parses/test_result.total_files*100):.1f}%")
    print()
    
    # Generate reports
    os.makedirs(output_dir, exist_ok=True)
    generate_report(test_result, output_dir)
    
    # Show quick summary of successful parses by client
    if test_result.successful_parses > 0:
        print("SUCCESS SUMMARY BY CLIENT:")
        print("-" * 40)
        clients = {}
        for result in test_result.results:
            if result["success"]:
                client_key = f"{result['client_info']['pan']} - {result['client_info']['client_name']}"
                if client_key not in clients:
                    clients[client_key] = []
                clients[client_key].append(result)
        
        for client, files in clients.items():
            print(f"{client}: {len(files)} file(s)")
            for file_result in files:
                stats = file_result["parsing_stats"]
                parts_list = ", ".join(file_result["data_summary"]["parts_with_data"])
                print(f"  • AY {file_result['client_info']['assessment_year']}: {stats['parts_with_data']} parts ({parts_list})")

if __name__ == "__main__":
    main()