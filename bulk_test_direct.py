"""
Direct Bulk Test Script
Uses the provided client data directly to run test_download.py for each client.
"""
import os
import sys
import subprocess
import time
from datetime import datetime

# Client data as provided
CLIENTS = [
    {"pan": "CDGPP3326R", "password": "Ing@1137", "dob": "07-Feb-89"},
    {"pan": "BIQPT8609H", "password": "Ing@1137", "dob": "01-Jan-65"},
    {"pan": "AIWPA6115G", "password": "Ing@1137", "dob": "09-Nov-76"},
    {"pan": "ASIPD7661E", "password": "Ing@1137", "dob": "15-Jan-67"},
    {"pan": "AHLPU2662E", "password": "Ing@1137", "dob": "10-Jul-75"},
    {"pan": "AODPR7988H", "password": "Ing@1137", "dob": "06-Jun-84"},
    {"pan": "BDQPK0363J", "password": "Ing@1137", "dob": "17-Mar-75"},
    {"pan": "DBPPS5425A", "password": "Ing@1137", "dob": "20-Apr-58"},
    {"pan": "AQRPD8621M", "password": "Ing@1137", "dob": "04-Aug-89"},
    {"pan": "AKXPI1815N", "password": "Ing@1137", "dob": "12-Sep-96"},
    {"pan": "AMIPR1349D", "password": "Ing@1137", "dob": "18-Dec-84"},
    {"pan": "ASHPM1179M", "password": "Ing@1137", "dob": "18-Mar-74"},
    {"pan": "ACJPK1346G", "password": "Ing@1137", "dob": "16-Oct-62"},
    {"pan": "BJZPM5736N", "password": "Ing@1137", "dob": "12-Sep-75"},
    {"pan": "AODPT6977Q", "password": "Ing@1137", "dob": "11-Oct-88"},
    {"pan": "DSAPS5307B", "password": "Ing@1137", "dob": "05-Sep-89"},
    {"pan": "AOQPR3128E", "password": "Ing@1820", "dob": "09-Jul-77"},
    {"pan": "ARMPG2124J", "password": "Ing@1137", "dob": "01-Jan-85"},
    {"pan": "AAPPW0842B", "password": "Ing@1137", "dob": "21-Mar-75"},
    {"pan": "ADHPT8265E", "password": "Ing@1137", "dob": "01-Jan-68"},
    {"pan": "CTQPK9322N", "password": "Ing@1137", "dob": "25-Dec-76"},
    {"pan": "AAOPI1287K", "password": "Ing@1137", "dob": "02-Dec-68"},
    {"pan": "AXKPM0717F", "password": "Ing@1137", "dob": "20-Aug-55"},
    {"pan": "ANBPG6588M", "password": "Ing@1137", "dob": "17-Dec-84"},
    {"pan": "DDSPK6942K", "password": "Ing@1137", "dob": "25-Jan-77"},
    {"pan": "ALIPD2666E", "password": "Ing@1210", "dob": "04-Jun-65"},
    {"pan": "LNHPS6734G", "password": "Ing@1137", "dob": "21-Dec-00"},
    {"pan": "BJWPK1927J", "password": "Ing@1137", "dob": "01-Sep-72"},
    {"pan": "ENNPK5934D", "password": "Ing@1137", "dob": "16-Mar-97"},
    {"pan": "ABAPU8947P", "password": "Ing@1137", "dob": "27-Dec-78"},
    {"pan": "AEGPC2938D", "password": "Ing@1137", "dob": "06-Nov-72"},
    {"pan": "ABDPC0700B", "password": "Ing@1210", "dob": "30-Mar-66"},
    {"pan": "AEGPC5471F", "password": "Ing@1137", "dob": "13-May-76"},
    {"pan": "AIPPK3522L", "password": "Ing@1137", "dob": "09-Apr-81"},
    {"pan": "BVAPS9030A", "password": "Ing@1137", "dob": "22-Sep-84"},
    {"pan": "AHGPJ4446C", "password": "Ing@1137", "dob": "16-Nov-67"},
    {"pan": "AQEPB5816F", "password": "Ing@1137", "dob": "03-Jan-78"},
    {"pan": "AMZPB9193J", "password": "Ing@1137", "dob": "15-Jul-79"},
    {"pan": "AKMPD1039Q", "password": "Ing@1137", "dob": "18-Jun-76"},
    {"pan": "BPRPB8919L", "password": "Ing@1137", "dob": "01-Jul-75"},
    {"pan": "BNNPK2717D", "password": "Ing@1137", "dob": "25-Sep-85"},
    {"pan": "IBOPK0910E", "password": "Ing@1137", "dob": "14-Dec-93"},
    {"pan": "AKZPK8869L", "password": "Ing@1137", "dob": "09-May-73"},
    {"pan": "CATPD5881R", "password": "Ing@1137", "dob": "02-May-89"},
    {"pan": "ATRPM7012J", "password": "Ing@1137", "dob": "30-Dec-74"},
    {"pan": "ETTPM9077B", "password": "Ing@1137", "dob": "14-Apr-02"},
    {"pan": "AONPK9228D", "password": "Ing@1137", "dob": "10-Sep-81"},
    {"pan": "ANCPG7860M", "password": "Ing@1137", "dob": "01-Jul-71"},
    {"pan": "AUZPA6853E", "password": "Ing@1137", "dob": "15-May-78"},
    {"pan": "BHCPP3683C", "password": "Ing@1137", "dob": "15-Jul-76"},
    {"pan": "CAUPB4344J", "password": "Ing@1137", "dob": "06-Aug-87"},
    {"pan": "ANKPG8242P", "password": "Ing@1137", "dob": "04-May-77"},
    {"pan": "BAWPG3818F", "password": "Ing@1137", "dob": "17-Jun-86"},
    {"pan": "AOHPN0437R", "password": "Ing@1137", "dob": "27-May-81"},
    {"pan": "ACXPY8016D", "password": "Ing@1137", "dob": "08-Aug-73"},
    {"pan": "AHAPT5100B", "password": "Ing@1137", "dob": "06-Jul-80"},
    {"pan": "ANGPV4022N", "password": "Ing@1137", "dob": "09-Nov-92"},
    {"pan": "AONPD0576P", "password": "Ing@1137", "dob": "12-Oct-80"},
    {"pan": "AEDPD0736M", "password": "Ing@1137", "dob": "01-Jan-75"},
    {"pan": "AIJPG6220B", "password": "Ing@1210", "dob": "24-Apr-65"},
    {"pan": "AMDPG4878K", "password": "Ing@1137", "dob": "03-Feb-71"},
    {"pan": "HNBPK4111H", "password": "Ing@1137", "dob": "19-Aug-00"},
    {"pan": "BCVPV7359H", "password": "Ing@1137", "dob": "01-Jan-63"},
    {"pan": "GNHPS6440E", "password": "Ing@1137", "dob": "05-Oct-83"},
    {"pan": "AYXPV5878Q", "password": "Ing@1137", "dob": "01-Nov-88"},
    {"pan": "CCTPG4135M", "password": "Ing@1137", "dob": "05-May-79"},
    {"pan": "ALWPD1654N", "password": "Ing@1137", "dob": "14-Dec-85"},
    {"pan": "CJHPM4428G", "password": "Ing@1137", "dob": "13-Apr-74"},
    {"pan": "BPIPB7221Q", "password": "Ing@1137", "dob": "30-Nov-78"},
    {"pan": "AUYPB9887E", "password": "Ing@1820", "dob": "05-May-77"},
    {"pan": "AUEPS6065K", "password": "Ing@1820", "dob": "31-Mar-78"}
]

def format_dob(dob_str):
    """Convert DOB from dd-MMM-yy to dd-mm-yyyy format."""
    try:
        # Parse the input date
        from datetime import datetime
        # Handle 2-digit years
        if len(dob_str.split('-')[2]) == 2:
            year = int(dob_str.split('-')[2])
            if year > 50:  # Assume 1950-1999 for years > 50
                year += 1900
            else:  # Assume 2000-2049 for years <= 50
                year += 2000
            dob_str = dob_str[:-2] + str(year)
        
        # Parse and reformat
        date_obj = datetime.strptime(dob_str, "%d-%b-%Y")
        return date_obj.strftime("%d-%m-%Y")
    except:
        # If parsing fails, return as-is
        return dob_str

def set_environment_for_client(client):
    """Set environment variables for the client."""
    os.environ["ITD_PAN"] = client["pan"]
    os.environ["ITD_PASSWORD"] = client["password"]
    os.environ["ITD_DOB"] = format_dob(client["dob"])
    os.environ["ITD_USER_ID"] = client["pan"]  # Use PAN as user ID
    os.environ["ITD_CLIENT_NAME"] = client["pan"]

def run_test_for_client(client, test_script_path):
    """Run test_download.py for a single client."""
    result = {
        "client": client,
        "success": False,
        "output": "",
        "error": "",
        "duration": 0,
        "return_code": -1
    }
    
    try:
        start_time = datetime.now()
        
        # Set environment variables
        set_environment_for_client(client)
        
        print(f"Running test for {client['pan']} (DOB: {format_dob(client['dob'])})")
        
        # Run the test script
        process = subprocess.run(
            [sys.executable, test_script_path],
            cwd=os.path.dirname(test_script_path),
            capture_output=True,
            text=True,
            timeout=900  # 15 minute timeout per client
        )
        
        end_time = datetime.now()
        result["duration"] = (end_time - start_time).total_seconds()
        result["output"] = process.stdout
        result["error"] = process.stderr
        result["return_code"] = process.returncode
        result["success"] = process.returncode == 0
        
        if result["success"]:
            print(f"  ✓ SUCCESS ({result['duration']:.1f}s)")
            # Extract key info from output
            if "26AS:" in result["output"]:
                for line in result["output"].split('\n'):
                    if "26AS:" in line or "AIS/TIS:" in line:
                        print(f"    {line.strip()}")
        else:
            print(f"  ✗ FAILED ({result['duration']:.1f}s)")
            if result["error"]:
                # Show first error line
                first_error = result["error"].split('\n')[0] if result["error"] else "Unknown error"
                print(f"    Error: {first_error}")
        
    except subprocess.TimeoutExpired:
        result["error"] = "Test timed out after 15 minutes"
        result["duration"] = 900
        print(f"  ✗ TIMEOUT (15 minutes)")
    except Exception as e:
        result["error"] = str(e)
        print(f"  ✗ ERROR: {e}")
    
    return result

def generate_summary_report(results, output_dir):
    """Generate a summary report of all test results."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(output_dir, f"bulk_test_summary_{timestamp}.txt")
    
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("BULK TEST SUMMARY REPORT\n")
        f.write("=" * 50 + "\n")
        f.write(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Clients: {len(results)}\n")
        f.write(f"Successful: {len(successful)}\n")
        f.write(f"Failed: {len(failed)}\n")
        f.write(f"Success Rate: {len(successful)/len(results)*100:.1f}%\n")
        f.write(f"Total Time: {sum(r['duration'] for r in results):.1f} seconds\n")
        f.write("\n")
        
        if successful:
            f.write("SUCCESSFUL DOWNLOADS:\n")
            f.write("-" * 30 + "\n")
            for result in successful:
                f.write(f"✓ {result['client']['pan']} ({result['duration']:.1f}s)\n")
        
        if failed:
            f.write(f"\nFAILED DOWNLOADS ({len(failed)}):\n")
            f.write("-" * 30 + "\n")
            for result in failed:
                f.write(f"✗ {result['client']['pan']} - {result['error'][:100]}...\n")
    
    print(f"\nSummary report saved to: {report_path}")

def main():
    test_script_path = r"C:\Users\Devansh\Desktop\Taxify\test_download.py"
    output_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("Direct Bulk Test Script")
    print("=" * 50)
    print(f"Test Script: {test_script_path}")
    print(f"Total Clients: {len(CLIENTS)}")
    print()
    
    # Check if test script exists
    if not os.path.exists(test_script_path):
        print(f"ERROR: Test script not found: {test_script_path}")
        return
    
    # Show first 5 clients
    print("First 5 clients:")
    for i, client in enumerate(CLIENTS[:5], 1):
        print(f"  {i}. {client['pan']} - {client['password']} - {client['dob']}")
    print(f"  ... and {len(CLIENTS) - 5} more clients\n")
    
    # Ask for confirmation
    response = input(f"Proceed with bulk testing for {len(CLIENTS)} clients? (y/N): ")
    if response.lower() != 'y':
        print("Cancelled by user")
        return
    
    # Store original environment
    original_env = {key: os.environ.get(key, "") for key in 
                   ["ITD_PAN", "ITD_PASSWORD", "ITD_DOB", "ITD_USER_ID", "ITD_CLIENT_NAME"]}
    
    results = []
    
    try:
        print(f"\nStarting bulk test for {len(CLIENTS)} clients...")
        print("=" * 80)
        
        for i, client in enumerate(CLIENTS, 1):
            print(f"\n[{i}/{len(CLIENTS)}] ", end="")
            result = run_test_for_client(client, test_script_path)
            results.append(result)
            
            # Small delay between clients (except for last one)
            if i < len(CLIENTS):
                print("Waiting 10 seconds before next client...")
                time.sleep(10)
    
    except KeyboardInterrupt:
        print("\n\nBulk test interrupted by user (Ctrl+C)")
    
    finally:
        # Restore original environment
        for key, value in original_env.items():
            if value:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]
    
    # Generate summary
    if results:
        successful = sum(1 for r in results if r["success"])
        total = len(results)
        total_time = sum(r["duration"] for r in results)
        
        print(f"\n\nBULK TEST COMPLETE")
        print("=" * 50)
        print(f"Results: {successful}/{total} clients successful ({successful/total*100:.1f}%)")
        print(f"Total Time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
        
        generate_summary_report(results, output_dir)
    else:
        print("No results to report")

if __name__ == "__main__":
    main()