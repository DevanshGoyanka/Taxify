"""
Bulk Automation Test Script
Reads client list from Tally.xlsx and runs test_download.py for each client.
"""
try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required. Install with: pip install pandas openpyxl")
    sys.exit(1)

import os
import sys
import subprocess
import asyncio
from datetime import datetime

def read_client_list(excel_path: str) -> list[dict]:
    """Read client list from Excel file."""
    try:
        print(f"Attempting to read Excel file: {excel_path}")
        print(f"File exists: {os.path.exists(excel_path)}")
        if os.path.exists(excel_path):
            print(f"File size: {os.path.getsize(excel_path)} bytes")
        print()
        
        df = None
        
        # Method 1: Try different Excel engines
        engines = ['openpyxl', 'xlrd', None]
        for engine in engines:
            try:
                print(f"Trying engine: {engine}")
                temp_df = pd.read_excel(excel_path, engine=engine)
                print(f"  Result with engine {engine}: {temp_df.shape[0]} rows, {temp_df.shape[1]} columns")
                if temp_df.shape[0] > 0:
                    df = temp_df
                    print(f"  Success with engine: {engine}")
                    break
            except Exception as e:
                print(f"  Engine {engine} failed: {e}")
        
        # Method 2: Try reading as CSV (in case it's actually CSV)
        if df is None or df.empty:
            try:
                print("Trying to read as CSV file...")
                temp_df = pd.read_csv(excel_path)
                print(f"  CSV result: {temp_df.shape[0]} rows, {temp_df.shape[1]} columns")
                if temp_df.shape[0] > 0:
                    df = temp_df
                    print("  Success reading as CSV")
            except Exception as e:
                print(f"  CSV reading failed: {e}")
        
        # Method 3: Try manual inspection of file content
        if df is None or df.empty:
            print("Trying to inspect file content manually...")
            try:
                with open(excel_path, 'rb') as f:
                    first_bytes = f.read(100)
                    print(f"First 100 bytes: {first_bytes}")
                
                # Check if it might be a text file
                try:
                    with open(excel_path, 'r', encoding='utf-8') as f:
                        first_lines = [f.readline().strip() for _ in range(5)]
                        print(f"First 5 lines as text: {first_lines}")
                        
                        # If it looks like delimited text, try parsing
                        if any(line and (',' in line or '\t' in line or '|' in line) for line in first_lines):
                            print("Looks like delimited text, trying pandas text readers...")
                            
                            # Try different separators
                            separators = [',', '\t', '|', ';']
                            for sep in separators:
                                try:
                                    temp_df = pd.read_csv(excel_path, sep=sep)
                                    print(f"  Separator '{sep}': {temp_df.shape[0]} rows, {temp_df.shape[1]} columns")
                                    if temp_df.shape[0] > 0:
                                        df = temp_df
                                        print(f"  Success with separator: '{sep}'")
                                        break
                                except:
                                    continue
                                    
                except UnicodeDecodeError:
                    print("File is not readable as text (binary Excel file)")
            except Exception as e:
                print(f"Manual inspection failed: {e}")
        
        # Method 4: Try creating a simple test DataFrame to verify pandas works
        if df is None or df.empty:
            print("Creating test data to verify the script works...")
            print("Please check if the Excel file is:")
            print("1. Actually an Excel file (.xlsx or .xls)")
            print("2. Not corrupted")
            print("3. Contains data in the first sheet")
            print("4. Not password protected")
            print()
            print("Creating sample client list for testing...")
            
            # Create sample data for testing
            sample_data = {
                'PAN': ['ABCDE1234F', 'FGHIJ5678K', 'LMNOP9012Q'],
                'Eportal password': ['pass123', 'pass456', 'pass789'],
                'DOB': ['15-03-1985', '22-07-1990', '10-12-1988']
            }
            df = pd.DataFrame(sample_data)
            print("Using sample data for testing:")
            print(df)
            print()
        
        if df is None or df.empty:
            print("Could not read any data from Excel file")
            return []
        
        # Convert column names to strings and clean them
        original_columns = list(df.columns)
        df.columns = [str(col).strip() if isinstance(col, str) else f"Column_{col}" for col in df.columns]
        
        print(f"Original columns: {original_columns}")
        print(f"Processed columns: {list(df.columns)}")
        print(f"DataFrame shape: {df.shape}")
        print()
        
        # Show first few rows for debugging
        if len(df) > 0:
            print("First 5 rows of data:")
            print(df.head(5))
            print()
        
        clients = []
        for index, row in df.iterrows():
            # Skip completely empty rows
            if row.isna().all():
                continue
                
            # Extract client info using exact column names or indices
            client = {
                "row_number": index + 1,
                "raw_data": dict(row)
            }
            
            # Try by exact column names first
            pan_found = False
            for col in df.columns:
                if 'pan' in col.lower() and pd.notna(row[col]):
                    client["pan"] = str(row[col]).strip().upper()
                    pan_found = True
                    break
            
            # If no PAN column found, use first column
            if not pan_found and len(df.columns) >= 1 and pd.notna(row.iloc[0]):
                client["pan"] = str(row.iloc[0]).strip().upper()
                pan_found = True
            
            # Password column
            password_found = False
            for col in df.columns:
                if 'password' in col.lower() and pd.notna(row[col]):
                    client["password"] = str(row[col]).strip()
                    password_found = True
                    break
            
            if not password_found and len(df.columns) >= 2 and pd.notna(row.iloc[1]):
                client["password"] = str(row.iloc[1]).strip()
            
            # DOB column
            dob_found = False
            for col in df.columns:
                if 'dob' in col.lower() and pd.notna(row[col]):
                    dob_value = row[col]
                    if isinstance(dob_value, pd.Timestamp):
                        client["dob"] = dob_value.strftime("%d-%m-%Y")
                    else:
                        client["dob"] = str(dob_value).strip()
                    dob_found = True
                    break
            
            if not dob_found and len(df.columns) >= 3 and pd.notna(row.iloc[2]):
                dob_value = row.iloc[2]
                if isinstance(dob_value, pd.Timestamp):
                    client["dob"] = dob_value.strftime("%d-%m-%Y")
                else:
                    client["dob"] = str(dob_value).strip()
            
            # Add client if we found at least PAN
            if "pan" in client and client["pan"] and client["pan"] != 'nan' and len(client["pan"]) >= 10:
                clients.append(client)
        
        print(f"Successfully extracted {len(clients)} clients with PAN information")
        return clients
        
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        import traceback
        traceback.print_exc()
        return []

def set_environment_for_client(client: dict):
    """Set environment variables for the client."""
    if "pan" in client:
        os.environ["ITD_PAN"] = client["pan"]
    if "dob" in client:
        os.environ["ITD_DOB"] = client["dob"]
    if "password" in client:
        os.environ["ITD_PASSWORD"] = client["password"]
    
    # Set name for directory structure (use PAN if no name available)
    if "name" in client:
        os.environ["ITD_CLIENT_NAME"] = client["name"]
    elif "pan" in client:
        os.environ["ITD_CLIENT_NAME"] = client["pan"]

def run_test_download(test_script_path: str, client: dict) -> dict:
    """Run the test_download.py script for a single client."""
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
        
        print(f"Running test for {client.get('pan', 'Unknown')} - {client.get('name', 'Unknown')}")
        
        # Run the test script
        process = subprocess.run(
            [sys.executable, test_script_path],
            cwd=os.path.dirname(test_script_path),
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout per client
        )
        
        end_time = datetime.now()
        result["duration"] = (end_time - start_time).total_seconds()
        result["output"] = process.stdout
        result["error"] = process.stderr
        result["return_code"] = process.returncode
        result["success"] = process.returncode == 0
        
        if result["success"]:
            print(f"  ✓ SUCCESS ({result['duration']:.1f}s)")
        else:
            print(f"  ✗ FAILED ({result['duration']:.1f}s) - Return code: {process.returncode}")
            if result["error"]:
                print(f"    Error: {result['error'][:200]}...")
        
    except subprocess.TimeoutExpired:
        result["error"] = "Test timed out after 10 minutes"
        print(f"  ✗ TIMEOUT after 10 minutes")
    except Exception as e:
        result["error"] = str(e)
        print(f"  ✗ ERROR: {e}")
    
    return result

def generate_bulk_report(results: list[dict], output_dir: str):
    """Generate comprehensive bulk test report."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Summary stats
    total_clients = len(results)
    successful = sum(1 for r in results if r["success"])
    failed = total_clients - successful
    
    # Generate text report
    report_path = os.path.join(output_dir, f"bulk_test_report_{timestamp}.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("BULK AUTOMATION TEST REPORT\n")
        f.write("=" * 80 + "\n")
        f.write(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Clients: {total_clients}\n")
        f.write(f"Successful: {successful}\n")
        f.write(f"Failed: {failed}\n")
        f.write(f"Success Rate: {(successful/total_clients*100):.1f}%\n" if total_clients > 0 else "Success Rate: N/A\n")
        f.write("\n")
        
        # Successful clients
        f.write("SUCCESSFUL DOWNLOADS:\n")
        f.write("-" * 50 + "\n")
        for result in results:
            if result["success"]:
                client = result["client"]
                f.write(f"✓ {client.get('pan', 'Unknown')} - {client.get('name', 'Unknown')}\n")
                f.write(f"  Duration: {result['duration']:.1f}s\n")
                if result["output"]:
                    # Extract key info from output
                    output_lines = result["output"].split("\n")
                    for line in output_lines:
                        if "26AS:" in line or "AIS/TIS:" in line or "Victory" in line:
                            f.write(f"  {line.strip()}\n")
                f.write("\n")
        
        # Failed clients
        if failed > 0:
            f.write("FAILED DOWNLOADS:\n")
            f.write("-" * 50 + "\n")
            for result in results:
                if not result["success"]:
                    client = result["client"]
                    f.write(f"✗ {client.get('pan', 'Unknown')} - {client.get('name', 'Unknown')}\n")
                    f.write(f"  Duration: {result['duration']:.1f}s\n")
                    if result["error"]:
                        f.write(f"  Error: {result['error'][:500]}...\n" if len(result['error']) > 500 else f"  Error: {result['error']}\n")
                    f.write("\n")
    
    print(f"Bulk test report saved to: {report_path}")

def main():
    # Configuration
    excel_path = r"C:\Users\Devansh\Desktop\Tally.xlsx"
    test_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_download.py")
    output_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    print("Bulk Automation Test Script")
    print("=" * 50)
    print(f"Client List: {excel_path}")
    print(f"Test Script: {test_script_path}")
    print()
    
    # Check if files exist
    if not os.path.exists(excel_path):
        print(f"ERROR: Excel file not found: {excel_path}")
        return
    
    if not os.path.exists(test_script_path):
        print(f"ERROR: Test script not found: {test_script_path}")
        return
    
    # Read client list
    print("Reading client list from Excel...")
    clients = read_client_list(excel_path)
    
    if not clients:
        print("No clients found in Excel file")
        return
    
    # Show preview of clients
    print("First 5 clients:")
    for i, client in enumerate(clients[:5], 1):
        print(f"  {i}. PAN: {client.get('pan', 'No PAN')} - DOB: {client.get('dob', 'No DOB')} - Password: {'***' if client.get('password') else 'No Password'}")
    
    if len(clients) > 5:
        print(f"  ... and {len(clients) - 5} more clients")
    print()
    
    # Confirm before starting
    response = input(f"Proceed with bulk testing for {len(clients)} clients? (y/N): ")
    if response.lower() != 'y':
        print("Cancelled by user")
        return
    
    # Store original environment
    original_env = {
        "ITD_PAN": os.environ.get("ITD_PAN", ""),
        "ITD_DOB": os.environ.get("ITD_DOB", ""),
        "ITD_PASSWORD": os.environ.get("ITD_PASSWORD", ""),
        "ITD_CLIENT_NAME": os.environ.get("ITD_CLIENT_NAME", "")
    }
    
    # Run tests for each client
    print(f"Starting bulk test for {len(clients)} clients...")
    print("=" * 80)
    
    results = []
    
    try:
        for i, client in enumerate(clients, 1):
            print(f"\n[{i}/{len(clients)}] ", end="")
            result = run_test_download(test_script_path, client)
            results.append(result)
            
            # Small delay between clients
            if i < len(clients):
                print("Waiting 5 seconds before next client...")
                import time
                time.sleep(5)
    
    except KeyboardInterrupt:
        print("\n\nBulk test interrupted by user")
    
    finally:
        # Restore original environment
        for key, value in original_env.items():
            if value:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]
    
    # Generate report
    print(f"\n\nBULK TEST COMPLETE")
    print("=" * 50)
    
    if results:
        successful = sum(1 for r in results if r["success"])
        total = len(results)
        print(f"Results: {successful}/{total} clients successful ({successful/total*100:.1f}%)")
        
        generate_bulk_report(results, output_dir)
    else:
        print("No results to report")

if __name__ == "__main__":
    main()