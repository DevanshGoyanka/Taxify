"""Debug script to test AIS PDF password patterns"""

import os
from datetime import datetime
import sys

try:
    import PyMuPDF as fitz
    PYMUPDF_AVAILABLE = True
    print("✓ PyMuPDF imported successfully")
except ImportError as e:
    PYMUPDF_AVAILABLE = False
    print(f"✗ PyMuPDF import failed: {e}")

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
    print("✓ pdfplumber imported successfully")
except ImportError as e:
    PDFPLUMBER_AVAILABLE = False
    print(f"✗ pdfplumber import failed: {e}")

def convert_dob_format(dob_str):
    """Convert DOB from DD-MMM-YY format to DDMMYYYY format"""
    if not dob_str:
        return []
        
    try:
        # Parse formats like "07-Feb-89", "01-Jan-65"
        formats_to_try = [
            "%d-%b-%y",   # 07-Feb-89
            "%d-%b-%Y",   # 07-Feb-1989
            "%d-%m-%Y",   # 07-02-1989
            "%d-%m-%y",   # 07-02-89
        ]
        
        parsed_date = None
        for fmt in formats_to_try:
            try:
                parsed_date = datetime.strptime(dob_str, fmt)
                break
            except ValueError:
                continue
        
        if not parsed_date:
            print(f"Could not parse DOB: {dob_str}")
            return []
        
        # Generate different DOB formats for password attempts
        dd = f"{parsed_date.day:02d}"
        mm = f"{parsed_date.month:02d}"
        yyyy = f"{parsed_date.year:04d}"
        yy = f"{parsed_date.year % 100:02d}"
        
        return [
            dd + mm + yyyy,  # DDMMYYYY - most common for AIS
            dd + mm + yy,    # DDMMYY - alternative
            f"{dd}/{mm}/{yyyy}",  # DD/MM/YYYY
        ]
        
    except Exception as e:
        print(f"Error parsing DOB {dob_str}: {e}")
        return []

def generate_passwords(pan, dob_str):
    """Generate all possible password combinations"""
    print(f"\nGenerating passwords for PAN: {pan}, DOB: {dob_str}")
    
    dob_formats = convert_dob_format(dob_str)
    print(f"DOB formats generated: {dob_formats}")
    
    passwords = []
    
    for dob_fmt in dob_formats:
        # AIS/TIS format: lowercase PAN + DDMMYYYY  
        passwords.append(f"{pan.lower()}{dob_fmt}")
        # Alternative formats
        passwords.extend([
            dob_fmt,  # DOB only
            f"{pan.upper()}{dob_fmt}",  # uppercase PAN + DOB
            pan.lower(),  # Just lowercase PAN
            pan.upper(),  # Just uppercase PAN
        ])
    
    # Remove duplicates while preserving order
    seen = set()
    unique_passwords = []
    for pwd in passwords:
        if pwd not in seen:
            unique_passwords.append(pwd)
            seen.add(pwd)
    
    return unique_passwords

def test_pdf_with_passwords(pdf_path, passwords):
    """Test a PDF with various passwords"""
    print(f"\nTesting PDF: {pdf_path}")
    print(f"File exists: {os.path.exists(pdf_path)}")
    
    if not os.path.exists(pdf_path):
        return False, "File not found"
    
    file_size = os.path.getsize(pdf_path)
    print(f"File size: {file_size} bytes")
    
    # Test with pdfplumber first
    if PDFPLUMBER_AVAILABLE:
        print(f"\nTesting {len(passwords)} passwords with pdfplumber...")
        for i, password in enumerate(passwords, 1):
            print(f"  {i:2d}. Trying password: '{password}'")
            try:
                with pdfplumber.open(pdf_path, password=password) as pdf:
                    page_count = len(pdf.pages)
                    print(f"      ✓ SUCCESS! Pages: {page_count}")
                    return True, f"Opened with pdfplumber using password '{password}', {page_count} pages"
            except Exception as e:
                error_msg = str(e).lower()
                if "password" in error_msg or "decrypt" in error_msg:
                    print(f"      ✗ Wrong password")
                else:
                    print(f"      ✗ Error: {e}")
    
    # Test with PyMuPDF if available
    if PYMUPDF_AVAILABLE:
        print(f"\nTesting {len(passwords)} passwords with PyMuPDF...")
        for i, password in enumerate(passwords, 1):
            print(f"  {i:2d}. Trying password: '{password}'")
            try:
                doc = fitz.open(pdf_path)
                if doc.authenticate(password):
                    page_count = len(doc)
                    doc.close()
                    print(f"      ✓ SUCCESS! Pages: {page_count}")
                    return True, f"Opened with PyMuPDF using password '{password}', {page_count} pages"
                else:
                    print(f"      ✗ Wrong password")
                doc.close()
            except Exception as e:
                print(f"      ✗ Error: {e}")
    
    return False, "No password worked"

def main():
    """Main test function"""
    
    # Test cases from the client data
    test_cases = [
        ("AAPPW0842B", "21-Mar-75"),
        ("ADHPT8265E", "01-Jan-68"),
        ("AEGPC2938D", "06-Nov-72"),
        ("CDGPP3326R", "07-Feb-89"),
        ("EPPPG3078Q", "01-Jan-90"),  # Made up for testing
    ]
    
    downloads_base = r"C:\Users\Devansh\Desktop\Taxify\downloads"
    
    for pan, dob in test_cases:
        print("="*80)
        print(f"TESTING: PAN {pan}, DOB {dob}")
        print("="*80)
        
        # Generate passwords
        passwords = generate_passwords(pan, dob)
        print(f"Generated {len(passwords)} password candidates:")
        for i, pwd in enumerate(passwords, 1):
            print(f"  {i:2d}. '{pwd}'")
        
        # Find the AIS PDF file for this PAN
        possible_paths = [
            f"{downloads_base}/{pan}-DEVANSH SUNIT GOYANKA/AY_2026_27/{pan}-AIS-2025_26.pdf",
            f"{downloads_base}/{pan}-AIS-2025_26.pdf"
        ]
        
        pdf_path = None
        for path in possible_paths:
            if os.path.exists(path):
                pdf_path = path
                break
        
        if not pdf_path:
            print(f"No AIS PDF found for {pan}")
            continue
        
        # Test the PDF
        success, message = test_pdf_with_passwords(pdf_path, passwords)
        
        print(f"\nRESULT: {message}")
        
        if success:
            print("🎉 Successfully opened PDF!")
            # Try to extract a sample of content
            try:
                if PDFPLUMBER_AVAILABLE:
                    working_password = message.split("'")[1]  # Extract password from message
                    with pdfplumber.open(pdf_path, password=working_password) as pdf:
                        if pdf.pages:
                            text = pdf.pages[0].extract_text()[:500]  # First 500 chars
                            print(f"\nFirst 500 characters of content:\n{text}")
                            
                            tables = pdf.pages[0].extract_tables()
                            print(f"Tables found on first page: {len(tables)}")
            except Exception as e:
                print(f"Error extracting sample content: {e}")
        else:
            print("❌ Failed to open PDF")
        
        break  # Only test the first case for now

if __name__ == "__main__":
    main()