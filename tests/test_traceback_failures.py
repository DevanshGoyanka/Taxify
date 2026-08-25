"""
Script to retry only the clients that had traceback errors (complete failures).
These are clients 34-71 that failed with "Error: Traceback" in the original test.
"""

import os
import sys
import subprocess
import time
from datetime import datetime

# Only clients that had traceback errors (complete failures)
TRACEBACK_FAILED_CLIENTS = [
    {"pan": "AIPPK3522L", "dob": "09-04-1981", "password": "Ing@1137"},
    {"pan": "BVAPS9030A", "dob": "22-09-1984", "password": "Ing@1137"},
    {"pan": "AHGPJ4446C", "dob": "16-11-1967", "password": "Ing@1137"},
    {"pan": "AQEPB5816F", "dob": "03-01-1978", "password": "Ing@1137"},
    {"pan": "AMZPB9193J", "dob": "15-07-1979", "password": "Ing@1137"},
    {"pan": "AKMPD1039Q", "dob": "18-06-1976", "password": "Ing@1137"},
    {"pan": "BPRPB8919L", "dob": "01-07-1975", "password": "Ing@1137"},
    {"pan": "BNNPK2717D", "dob": "25-09-1985", "password": "Ing@1137"},
    {"pan": "IBOPK0910E", "dob": "14-12-1993", "password": "Ing@1137"},
    {"pan": "AKZPK8869L", "dob": "09-05-1973", "password": "Ing@1137"},
    {"pan": "CATPD5881R", "dob": "02-05-1989", "password": "Ing@1137"},
    {"pan": "ATRPM7012J", "dob": "30-12-1974", "password": "Ing@1137"},
    {"pan": "ETTPM9077B", "dob": "14-04-2002", "password": "Ing@1137"},
    {"pan": "AONPK9228D", "dob": "10-09-1981", "password": "Ing@1137"},
    {"pan": "ANCPG7860M", "dob": "01-07-1971", "password": "Ing@1137"},
    {"pan": "AUZPA6853E", "dob": "15-05-1978", "password": "Ing@1137"},
    {"pan": "BHCPP3683C", "dob": "15-07-1976", "password": "Ing@1137"},
    {"pan": "CAUPB4344J", "dob": "06-08-1987", "password": "Ing@1137"},
    {"pan": "ANKPG8242P", "dob": "04-05-1977", "password": "Ing@1137"},
    {"pan": "BAWPG3818F", "dob": "17-06-1986", "password": "Ing@1137"},
    {"pan": "AOHPN0437R", "dob": "27-05-1981", "password": "Ing@1137"},
    {"pan": "ACXPY8016D", "dob": "08-08-1973", "password": "Ing@1137"},
    {"pan": "AHAPT5100B", "dob": "06-07-1980", "password": "Ing@1137"},
    {"pan": "ANGPV4022N", "dob": "09-11-1992", "password": "Ing@1137"},
    {"pan": "AONPD0576P", "dob": "12-10-1980", "password": "Ing@1137"},
    {"pan": "AEDPD0736M", "dob": "01-01-1975", "password": "Ing@1137"},
    {"pan": "AIJPG6220B", "dob": "24-04-1965", "password": "Ing@1137"},
    {"pan": "AMDPG4878K", "dob": "03-02-1971", "password": "Ing@1137"},
    {"pan": "HNBPK4111H", "dob": "19-08-2000", "password": "Ing@1137"},
    {"pan": "BCVPV7359H", "dob": "01-01-1963", "password": "Ing@1137"},
    {"pan": "GNHPS6440E", "dob": "05-10-1983", "password": "Ing@1137"},
    {"pan": "AYXPV5878Q", "dob": "01-11-1988", "password": "Ing@1137"},
    {"pan": "CCTPG4135M", "dob": "05-05-1979", "password": "Ing@1137"},
    {"pan": "ALWPD1654N", "dob": "14-12-1985", "password": "Ing@1137"},
    {"pan": "CJHPM4428G", "dob": "13-04-1974", "password": "Ing@1137"},
    {"pan": "BPIPB7221Q", "dob": "30-11-1978", "password": "Ing@1137"},
    {"pan": "AUYPB9887E", "dob": "05-05-1977", "password": "Ing@1137"},
    {"pan": "AUEPS6065K", "dob": "31-03-1978", "password": "Ing@1137"}
]

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
        "duration": 0
    }
    
    try:
        start_time = datetime.now()
        
        # Set environment variables
        set_environment_for_client(client)
        
        # Run the test script
        process = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_download.py")],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
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
                elif "[Error]" in line:
                    result["error_message"] = line.strip()
        
        if result["success"]:
            print(f"✓ SUCCESS ({result['duration']:.1f}s)")
            if result.get("26as_status"):
                print(f"{result['26as_status']}")
            if result.get("ais_status"):
                print(f"{result['ais_status']}")
        else:
            print(f"✗ FAILED ({result['duration']:.1f}s)")
            if result.get("error_message"):
                print(f"{result['error_message']}")
            elif result["error"]:
                # Show first line of error
                error_lines = result["error"].strip().split('\n')
                if error_lines:
                    print(f"Error: {error_lines[0][:100]}...")
        
    except subprocess.TimeoutExpired:
        result["error"] = "Test timed out after 5 minutes"
        result["duration"] = 300
        print(f"✗ TIMEOUT after 5 minutes")
    except Exception as e:
        result["error"] = str(e)
        print(f"✗ ERROR: {e}")
    
    return result

def generate_summary_report(results: list[dict]):
    """Generate a summary report of the retry results."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"traceback_failures_retry_summary_{timestamp}.txt"
    
    total = len(results)
    successful = sum(1 for r in results if r["success"])
    failed = total - successful
    total_time = sum(r["duration"] for r in results)
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("TRACEBACK FAILURES RETRY SUMMARY\n")
        f.write("=" * 50 + "\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Clients: {total}\n")
        f.write(f"Successful: {successful}\n")
        f.write(f"Failed: {failed}\n")
        f.write(f"Success Rate: {(successful/total*100):.1f}%\n" if total > 0 else "Success Rate: N/A\n")
        f.write(f"Total Time: {total_time:.0f} seconds ({total_time/60:.1f} minutes)\n")
        f.write("\n")
        
        if successful > 0:
            f.write("SUCCESSFUL:\n")
            f.write("-" * 20 + "\n")
            for result in results:
                if result["success"]:
                    client = result["client"]
                    f.write(f"✓ {client['pan']} ({result['duration']:.1f}s)\n")
        
        if failed > 0:
            f.write("\nSTILL FAILED:\n")
            f.write("-" * 20 + "\n")
            for result in results:
                if not result["success"]:
                    client = result["client"]
                    f.write(f"✗ {client['pan']} ({result['duration']:.1f}s)\n")
    
    print(f"Summary report saved to: {report_path}")

def main():
    print("Traceback Failures Retry Script")
    print("=" * 50)
    print(f"Retrying {len(TRACEBACK_FAILED_CLIENTS)} clients that had traceback errors")
    print("These were clients 34-71 from the original bulk test")
    print()
    
    # Show first 5 clients
    print("First 5 clients to retry:")
    for i, client in enumerate(TRACEBACK_FAILED_CLIENTS[:5], 1):
        print(f"  {i}. {client['pan']} (DOB: {client['dob']})")
    if len(TRACEBACK_FAILED_CLIENTS) > 5:
        print(f"  ... and {len(TRACEBACK_FAILED_CLIENTS) - 5} more clients")
    print()
    
    # Confirm before starting
    response = input(f"Proceed with retry for {len(TRACEBACK_FAILED_CLIENTS)} clients? (y/N): ")
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
    print(f"Starting retry for {len(TRACEBACK_FAILED_CLIENTS)} clients...")
    print("=" * 80)
    
    results = []
    start_time = datetime.now()
    
    try:
        for i, client in enumerate(TRACEBACK_FAILED_CLIENTS, 1):
            print(f"[{i}/{len(TRACEBACK_FAILED_CLIENTS)}] Running test for {client['pan']} (DOB: {client['dob']})")
            result = run_test_for_client(client)
            results.append(result)
            
            # Wait between clients (except for the last one)
            if i < len(TRACEBACK_FAILED_CLIENTS):
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
    
    print(f"\n\nTRACEBACK FAILURES RETRY COMPLETE")
    print("=" * 50)
    
    if results:
        successful = sum(1 for r in results if r["success"])
        failed = len(results) - successful
        
        print(f"Results: {successful}/{len(results)} clients successful ({successful/len(results)*100:.1f}%)")
        print(f"Total Time: {total_time:.0f} seconds ({total_time/60:.1f} minutes)")
        
        generate_summary_report(results)
    else:
        print("No results to report")

if __name__ == "__main__":
    main()