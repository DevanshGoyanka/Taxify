"""
Script to rerun tests only for failed clients from the bulk test.
Does not redownload for clients that were already successfully downloaded.
"""

import os
import sys
import subprocess
import time
from datetime import datetime

# Failed clients from the bulk test output
FAILED_CLIENTS = [
    # Clients with specific download issues (not complete failures)
    {"pan": "ASIPD7661E", "dob": "15-01-1967", "password": "Ing@1137", "reason": "Could not find AssessmentYearDropDown on TRACES view26AS page"},
    {"pan": "AHLPU2662E", "dob": "10-07-1975", "password": "Ing@1137", "reason": "AIS/TIS status: requested"},
    {"pan": "AODPR7988H", "dob": "06-06-1984", "password": "Ing@1137", "reason": "Could not find AssessmentYearDropDown on TRACES view26AS page"},
    {"pan": "DBPPS5425A", "dob": "20-04-1958", "password": "Ing@1137", "reason": "Could not find AssessmentYearDropDown on TRACES view26AS page"},
    {"pan": "AMIPR1349D", "dob": "18-12-1984", "password": "Ing@1137", "reason": "AIS download icon not found or modal did not open"},
    {"pan": "AAOPI1287K", "dob": "02-12-1968", "password": "Ing@1137", "reason": "Could not find AssessmentYearDropDown on TRACES view26AS page"},
    {"pan": "ABDPC0700B", "dob": "30-03-1966", "password": "Ing@1137", "reason": "Could not find AssessmentYearDropDown on TRACES view26AS page"},
    {"pan": "ENNPK5934D", "dob": "16-03-1997", "password": "Ing@1137", "reason": "Could not find AssessmentYearDropDown on TRACES view26AS page"},
    
    # Clients with traceback errors (complete failures)
    {"pan": "AIPPK3522L", "dob": "09-04-1981", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "BVAPS9030A", "dob": "22-09-1984", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "AHGPJ4446C", "dob": "16-11-1967", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "AQEPB5816F", "dob": "03-01-1978", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "AMZPB9193J", "dob": "15-07-1979", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "AKMPD1039Q", "dob": "18-06-1976", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "BPRPB8919L", "dob": "01-07-1975", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "BNNPK2717D", "dob": "25-09-1985", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "IBOPK0910E", "dob": "14-12-1993", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "AKZPK8869L", "dob": "09-05-1973", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "CATPD5881R", "dob": "02-05-1989", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "ATRPM7012J", "dob": "30-12-1974", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "ETTPM9077B", "dob": "14-04-2002", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "AONPK9228D", "dob": "10-09-1981", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "ANCPG7860M", "dob": "01-07-1971", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "AUZPA6853E", "dob": "15-05-1978", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "BHCPP3683C", "dob": "15-07-1976", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "CAUPB4344J", "dob": "06-08-1987", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "ANKPG8242P", "dob": "04-05-1977", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "BAWPG3818F", "dob": "17-06-1986", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "AOHPN0437R", "dob": "27-05-1981", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "ACXPY8016D", "dob": "08-08-1973", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "AHAPT5100B", "dob": "06-07-1980", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "ANGPV4022N", "dob": "09-11-1992", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "AONPD0576P", "dob": "12-10-1980", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "AEDPD0736M", "dob": "01-01-1975", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "AIJPG6220B", "dob": "24-04-1965", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "AMDPG4878K", "dob": "03-02-1971", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "HNBPK4111H", "dob": "19-08-2000", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "BCVPV7359H", "dob": "01-01-1963", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "GNHPS6440E", "dob": "05-10-1983", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "AYXPV5878Q", "dob": "01-11-1988", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "CCTPG4135M", "dob": "05-05-1979", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "ALWPD1654N", "dob": "14-12-1985", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "CJHPM4428G", "dob": "13-04-1974", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "BPIPB7221Q", "dob": "30-11-1978", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "AUYPB9887E", "dob": "05-05-1977", "password": "Ing@1137", "reason": "Traceback error"},
    {"pan": "AUEPS6065K", "dob": "31-03-1978", "password": "Ing@1137", "reason": "Traceback error"}
]

def check_if_downloaded(pan: str) -> tuple[bool, str]:
    """Check if files were already downloaded for this PAN."""
    downloads_root = r"C:\Users\Devansh\Desktop\Taxify\downloads"
    client_folder = f"{pan}-DEVANSH SUNIT GOYANKA"
    ay_folder = os.path.join(downloads_root, client_folder, "AY_2026_27")
    
    if not os.path.exists(ay_folder):
        return False, "No download folder found"
    
    # Check for downloaded files
    files_found = []
    for filename in os.listdir(ay_folder):
        if filename.startswith(pan):
            files_found.append(filename)
    
    if not files_found:
        return False, "Download folder exists but no files found"
    
    # Check for specific file types
    has_26as = any("26AS" in f for f in files_found)
    has_ais = any("AIS" in f for f in files_found)
    has_tis = any("TIS" in f for f in files_found)
    
    status = []
    if has_26as:
        status.append("26AS")
    if has_ais:
        status.append("AIS")
    if has_tis:
        status.append("TIS")
    
    if status:
        return True, f"Found: {', '.join(status)} ({len(files_found)} files)"
    else:
        return False, f"Found {len(files_found)} files but none are 26AS/AIS/TIS"

def set_environment_for_client(client: dict):
    """Set environment variables for the client."""
    os.environ["ITD_PAN"] = client["pan"]
    os.environ["ITD_DOB"] = client["dob"]  
    os.environ["ITD_PASSWORD"] = client["password"]
    # Set the user ID to the client's PAN
    os.environ["ITD_USER_ID"] = client["pan"]

def run_test_for_client(client: dict) -> dict:
    """Run test for a single client."""
    result = {
        "client": client,
        "success": False,
        "output": "",
        "error": "",
        "duration": 0,
        "skipped": False,
        "skip_reason": ""
    }
    
    try:
        # Check if already downloaded
        downloaded, status = check_if_downloaded(client["pan"])
        if downloaded:
            result["skipped"] = True
            result["skip_reason"] = f"Already downloaded: {status}"
            print(f"  ⚠ SKIPPED - {status}")
            return result
        
        start_time = datetime.now()
        
        # Set environment variables
        set_environment_for_client(client)
        
        # Run the test script
        process = subprocess.run(
            [sys.executable, "test_download.py"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout per client
        )
        
        end_time = datetime.now()
        result["duration"] = (end_time - start_time).total_seconds()
        result["output"] = process.stdout
        result["error"] = process.stderr
        result["return_code"] = process.returncode
        result["success"] = process.returncode == 0
        
        # Parse output for better reporting
        if result["output"]:
            lines = result["output"].split("\n")
            for line in lines:
                if "26AS:" in line:
                    result["26as_status"] = line.strip()
                elif "AIS/TIS:" in line:
                    result["ais_status"] = line.strip()
                elif "Error]" in line:
                    result["error_message"] = line.strip()
        
        if result["success"]:
            print(f"  ✓ SUCCESS ({result['duration']:.1f}s)")
            if result.get("26as_status"):
                print(f"    {result['26as_status']}")
            if result.get("ais_status"):
                print(f"    {result['ais_status']}")
        else:
            print(f"  ✗ FAILED ({result['duration']:.1f}s)")
            if result.get("error_message"):
                print(f"    {result['error_message']}")
            elif result["error"]:
                # Show first line of error
                error_lines = result["error"].strip().split('\n')
                if error_lines:
                    print(f"    Error: {error_lines[0][:100]}...")
        
    except subprocess.TimeoutExpired:
        result["error"] = "Test timed out after 5 minutes"
        result["duration"] = 300
        print(f"  ✗ TIMEOUT after 5 minutes")
    except Exception as e:
        result["error"] = str(e)
        print(f"  ✗ ERROR: {e}")
    
    return result

def generate_report(results: list[dict]):
    """Generate a report of the retry results."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"failed_clients_retry_report_{timestamp}.txt"
    
    total = len(results)
    successful = sum(1 for r in results if r["success"])
    skipped = sum(1 for r in results if r["skipped"])
    failed = total - successful - skipped
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("FAILED CLIENTS RETRY REPORT\n")
        f.write("=" * 80 + "\n")
        f.write(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Clients: {total}\n")
        f.write(f"Successful: {successful}\n")
        f.write(f"Skipped: {skipped}\n")
        f.write(f"Failed: {failed}\n")
        if total > 0:
            f.write(f"Success Rate: {(successful/(total-skipped)*100):.1f}%\n" if (total-skipped) > 0 else "Success Rate: N/A (all skipped)\n")
        f.write("\n")
        
        # Skipped clients
        if skipped > 0:
            f.write("SKIPPED (Already Downloaded):\n")
            f.write("-" * 50 + "\n")
            for result in results:
                if result["skipped"]:
                    client = result["client"]
                    f.write(f"⚠ {client['pan']} - {result['skip_reason']}\n")
            f.write("\n")
        
        # Successful retries
        if successful > 0:
            f.write("SUCCESSFUL RETRIES:\n")
            f.write("-" * 50 + "\n")
            for result in results:
                if result["success"]:
                    client = result["client"]
                    f.write(f"✓ {client['pan']} - Duration: {result['duration']:.1f}s\n")
                    if result.get("26as_status"):
                        f.write(f"  {result['26as_status']}\n")
                    if result.get("ais_status"):
                        f.write(f"  {result['ais_status']}\n")
            f.write("\n")
        
        # Still failed
        if failed > 0:
            f.write("STILL FAILED:\n")
            f.write("-" * 50 + "\n")
            for result in results:
                if not result["success"] and not result["skipped"]:
                    client = result["client"]
                    f.write(f"✗ {client['pan']} - Duration: {result['duration']:.1f}s\n")
                    f.write(f"  Original issue: {client.get('reason', 'Unknown')}\n")
                    if result.get("error_message"):
                        f.write(f"  New error: {result['error_message']}\n")
                    elif result["error"]:
                        error_lines = result["error"].strip().split('\n')
                        if error_lines:
                            f.write(f"  Error: {error_lines[0][:200]}...\n")
            f.write("\n")
    
    print(f"\nRetry report saved to: {report_path}")

def main():
    print("Failed Clients Retry Script")
    print("=" * 50)
    print(f"Total failed clients to retry: {len(FAILED_CLIENTS)}")
    print()
    
    # Show first 5 clients
    print("First 5 failed clients:")
    for i, client in enumerate(FAILED_CLIENTS[:5], 1):
        print(f"  {i}. {client['pan']} (DOB: {client['dob']}) - {client['reason']}")
    if len(FAILED_CLIENTS) > 5:
        print(f"  ... and {len(FAILED_CLIENTS) - 5} more clients")
    print()
    
    # Quick check to see how many are already downloaded
    already_downloaded = 0
    for client in FAILED_CLIENTS:
        downloaded, _ = check_if_downloaded(client["pan"])
        if downloaded:
            already_downloaded += 1
    
    if already_downloaded > 0:
        print(f"Note: {already_downloaded} clients appear to have files already downloaded and will be skipped.")
        print()
    
    # Confirm before starting
    response = input(f"Proceed with retry for {len(FAILED_CLIENTS)} failed clients? (y/N): ")
    if response.lower() != 'y':
        print("Cancelled by user")
        return
    
    # Check if test script exists
    if not os.path.exists("test_download.py"):
        print("ERROR: test_download.py not found in current directory")
        return
    
    # Store original environment
    original_env = {
        key: os.environ.get(key, "") for key in 
        ["ITD_PAN", "ITD_DOB", "ITD_PASSWORD", "ITD_USER_ID"]
    }
    
    # Run retry tests
    print(f"Starting retry for {len(FAILED_CLIENTS)} failed clients...")
    print("=" * 80)
    
    results = []
    start_time = datetime.now()
    
    try:
        for i, client in enumerate(FAILED_CLIENTS, 1):
            print(f"\n[{i}/{len(FAILED_CLIENTS)}] Running retry for {client['pan']} (DOB: {client['dob']})")
            result = run_test_for_client(client)
            results.append(result)
            
            # Wait between clients (only if not skipped and not the last client)
            if not result["skipped"] and i < len(FAILED_CLIENTS):
                print("Waiting 10 seconds before next client...")
                time.sleep(10)
    
    except KeyboardInterrupt:
        print("\n\nRetry interrupted by user")
    
    finally:
        # Restore original environment
        for key, value in original_env.items():
            if value:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]
    
    # Generate report
    end_time = datetime.now()
    total_time = (end_time - start_time).total_seconds()
    
    print(f"\n\nFAILED CLIENTS RETRY COMPLETE")
    print("=" * 50)
    
    if results:
        successful = sum(1 for r in results if r["success"])
        skipped = sum(1 for r in results if r["skipped"])
        failed = len(results) - successful - skipped
        
        print(f"Results: {successful} successful, {skipped} skipped, {failed} still failed")
        print(f"Total Time: {total_time:.0f} seconds ({total_time/60:.1f} minutes)")
        
        generate_report(results)
    else:
        print("No results to report")

if __name__ == "__main__":
    main()