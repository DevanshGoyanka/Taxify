"""
AIS PDF Structure Analysis Script

This script analyzes all AIS PDFs in the downloads directory to understand:
1. Document structure variations
2. Table layout patterns  
3. Section headers and organization
4. Password protection patterns
5. Multi-page table behavior
6. Content variations across different taxpayers

Analysis results will help design the optimal extraction strategy.
"""

import os
import glob
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import traceback

# Import the libraries we want to compare
try:
    import PyMuPDF as fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True  
except ImportError:
    PDFPLUMBER_AVAILABLE = False

@dataclass
class PDFAnalysisResult:
    """Results from analyzing a single AIS PDF."""
    file_path: str
    pan: Optional[str] = None
    file_size_mb: float = 0.0
    page_count: int = 0
    is_password_protected: bool = False
    password_worked: bool = False
    tried_passwords: List[str] = field(default_factory=list)
    
    # Structure analysis
    has_tables: bool = False
    table_count: int = 0
    sections_found: List[str] = field(default_factory=list)
    
    # PyMuPDF specific
    pymupdf_success: bool = False
    pymupdf_tables_found: int = 0
    pymupdf_extraction_time: float = 0.0
    
    # pdfplumber specific  
    pdfplumber_success: bool = False
    pdfplumber_tables_found: int = 0
    pdfplumber_extraction_time: float = 0.0
    
    # Content analysis
    sample_headers: List[str] = field(default_factory=list)
    sample_table_structure: Dict[str, Any] = field(default_factory=dict)
    
    # Error information
    errors: List[str] = field(default_factory=list)

class AISPDFAnalyzer:
    """Analyze AIS PDFs to understand structure variations."""
    
    def __init__(self, downloads_path: str):
        self.downloads_path = Path(downloads_path)
        self.results: List[PDFAnalysisResult] = []
        
    def get_client_dob(self, pan: str) -> Optional[str]:
        """Get DOB for a specific PAN from known client data."""
        # Client data from bulk_test_direct.py
        client_data = {
            "CDGPP3326R": "07-Feb-89",
            "BIQPT8609H": "01-Jan-65", 
            "AIWPA6115G": "09-Nov-76",
            "ASIPD7661E": "15-Jan-67",
            "AHLPU2662E": "10-Jul-75",
            "AODPR7988H": "06-Jun-84",
            "BDQPK0363J": "17-Mar-75",
            "DBPPS5425A": "20-Apr-58",
            "AQRPD8621M": "04-Aug-89",
            "AKXPI1815N": "12-Sep-96",
            "AMIPR1349D": "18-Dec-84",
            "ASHPM1179M": "18-Mar-74",
            "ACJPK1346G": "16-Oct-62",
            "BJZPM5736N": "12-Sep-75",
            "AODPT6977Q": "11-Oct-88",
            "DSAPS5307B": "05-Sep-89",
            "AOQPR3128E": "09-Jul-77",
            "ARMPG2124J": "01-Jan-85",
            "AAPPW0842B": "21-Mar-75",
            "ADHPT8265E": "01-Jan-68",
            "CTQPK9322N": "25-Dec-76",
            "AAOPI1287K": "02-Dec-68",
            "AXKPM0717F": "20-Aug-55",
            "ANBPG6588M": "17-Dec-84",
            "DDSPK6942K": "25-Jan-77",
            "ALIPD2666E": "04-Jun-65",
            "LNHPS6734G": "21-Dec-00",
            "BJWPK1927J": "01-Sep-72",
            "ENNPK5934D": "16-Mar-97",
            "ABAPU8947P": "27-Dec-78",
            "AEGPC2938D": "06-Nov-72",
            "ABDPC0700B": "30-Mar-66",
            "AEGPC5471F": "13-May-76",
            "AIPPK3522L": "09-Apr-81",
            "BVAPS9030A": "22-Sep-84",
            "AHGPJ4446C": "16-Nov-67",
            "AQEPB5816F": "03-Jan-78",
            "AMZPB9193J": "15-Jul-79",
            "AKMPD1039Q": "18-Jun-76",
            "BPRPB8919L": "01-Jul-75",
            "BNNPK2717D": "25-Sep-85",
            "IBOPK0910E": "14-Dec-93",
            "AKZPK8869L": "09-May-73",
            "CATPD5881R": "02-May-89",
            "ATRPM7012J": "30-Dec-74",
            "ETTPM9077B": "14-Apr-02",
            "AONPK9228D": "10-Sep-81",
            "ANCPG7860M": "01-Jul-71",
            "AUZPA6853E": "15-May-78",
            "BHCPP3683C": "15-Jul-76",
            "CAUPB4344J": "06-Aug-87",
            "ANKPG8242P": "04-May-77",
            "EPPPG3078Q": "01-Jan-90",  # Adding a test case
        }
        return client_data.get(pan)

    def convert_dob_format(self, dob_str: str) -> List[str]:
        """Convert DOB from DD-MMM-YY format to various formats needed for passwords."""
        if not dob_str:
            return []
            
        try:
            # Parse formats like "07-Feb-89", "01-Jan-65"
            from datetime import datetime
            
            # Handle various input formats
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
            
        except Exception:
            return []

    def generate_potential_passwords(self, pan: str) -> List[str]:
        """Generate potential passwords for AIS PDFs using actual client DOB data."""
        
        # Get the actual DOB for this PAN
        dob_str = self.get_client_dob(pan)
        if not dob_str:
            # Fallback to common test dates
            test_dates = ["01011990", "15081990", "01011985", "31121990"]
            passwords = [pan] + test_dates
            for date in test_dates:
                passwords.extend([
                    f"{pan.lower()}{date}",  # lowercase PAN + DOB (AIS format)
                    f"{pan.upper()}{date}",  # uppercase PAN + DOB
                    date,  # DOB only
                ])
            return passwords
        
        # Convert DOB to password formats
        dob_formats = self.convert_dob_format(dob_str)
        
        passwords = []
        seen = set()
        
        for dob_fmt in dob_formats:
            # AIS/TIS format: lowercase PAN + DDMMYYYY
            pwd = f"{pan.lower()}{dob_fmt}"
            if pwd not in seen:
                passwords.append(pwd)
                seen.add(pwd)
                
            # Alternative formats
            for alt_pwd in [
                dob_fmt,  # DOB only (26AS format)
                f"{pan.upper()}{dob_fmt}",  # uppercase PAN + DOB
                pan.lower(),  # Just lowercase PAN
                pan.upper(),  # Just uppercase PAN
            ]:
                if alt_pwd not in seen:
                    passwords.append(alt_pwd)
                    seen.add(alt_pwd)
        
        return passwords
    
    def extract_pan_from_filename(self, filepath: str) -> Optional[str]:
        """Extract PAN from filename."""
        filename = Path(filepath).name
        # PAN pattern: 5 letters + 4 digits + 1 letter
        match = re.search(r'([A-Z]{5}[0-9]{4}[A-Z])', filename)
        return match.group(1) if match else None
    
    def try_open_pdf(self, filepath: str, passwords: List[str]) -> tuple[Any, str, List[str]]:
        """Try to open PDF with various passwords."""
        tried_passwords = []
        
        # First try without password
        try:
            if PYMUPDF_AVAILABLE:
                doc = fitz.open(filepath)
                if not doc.is_encrypted:
                    return doc, "", tried_passwords
                doc.close()
        except:
            pass
            
        # Try with passwords
        for password in passwords:
            tried_passwords.append(password)
            try:
                if PYMUPDF_AVAILABLE:
                    doc = fitz.open(filepath)
                    if doc.authenticate(password):
                        return doc, password, tried_passwords
                    doc.close()
            except Exception as e:
                continue
                
        return None, "", tried_passwords
    
    def analyze_pymupdf(self, filepath: str, password: str) -> Dict[str, Any]:
        """Analyze PDF using PyMuPDF."""
        result = {
            'success': False,
            'tables_found': 0,
            'extraction_time': 0.0,
            'sample_content': [],
            'errors': []
        }
        
        if not PYMUPDF_AVAILABLE:
            result['errors'].append("PyMuPDF not available")
            return result
            
        try:
            import time
            start_time = time.time()
            
            doc = fitz.open(filepath)
            if password:
                doc.authenticate(password)
                
            tables_found = 0
            sample_content = []
            
            # Analyze first few pages
            for page_num in range(min(3, len(doc))):
                page = doc[page_num]
                
                # Try to find tables (if available in this version)
                try:
                    if hasattr(page, 'find_tables'):
                        tables = page.find_tables()
                        tables_found += len(tables)
                        
                        # Get sample from first table
                        if tables and len(sample_content) < 3:
                            first_table = tables[0]
                            sample_data = first_table.extract()
                            sample_content.append({
                                'page': page_num + 1,
                                'table_rows': len(sample_data) if sample_data else 0,
                                'table_cols': len(sample_data[0]) if sample_data and sample_data[0] else 0,
                                'sample_row': sample_data[0] if sample_data else []
                            })
                except Exception as e:
                    result['errors'].append(f"Table extraction error on page {page_num + 1}: {str(e)}")
                
                # Get text content for analysis
                try:
                    text = page.get_text()
                    if "Tax Deducted at Source" in text or "Tax Collected at Source" in text:
                        # Extract sample headers
                        lines = text.split('\n')[:20]  # First 20 lines
                        sample_content.append({
                            'page': page_num + 1,
                            'type': 'text_sample',
                            'content': [line.strip() for line in lines if line.strip()][:10]
                        })
                except Exception as e:
                    result['errors'].append(f"Text extraction error on page {page_num + 1}: {str(e)}")
            
            doc.close()
            
            result.update({
                'success': True,
                'tables_found': tables_found,
                'extraction_time': time.time() - start_time,
                'sample_content': sample_content
            })
            
        except Exception as e:
            result['errors'].append(f"PyMuPDF analysis failed: {str(e)}")
            
        return result
    
    def analyze_pdfplumber(self, filepath: str, password: str) -> Dict[str, Any]:
        """Analyze PDF using pdfplumber."""
        result = {
            'success': False,
            'tables_found': 0,
            'extraction_time': 0.0,
            'sample_content': [],
            'errors': []
        }
        
        if not PDFPLUMBER_AVAILABLE:
            result['errors'].append("pdfplumber not available")
            return result
            
        try:
            import time
            start_time = time.time()
            
            open_kwargs = {'password': password} if password else {}
            
            with pdfplumber.open(filepath, **open_kwargs) as pdf:
                tables_found = 0
                sample_content = []
                
                # Analyze first few pages
                for page_num, page in enumerate(pdf.pages[:3]):
                    try:
                        # Extract tables
                        tables = page.extract_tables()
                        tables_found += len(tables)
                        
                        # Get sample from first table
                        if tables and len(sample_content) < 3:
                            first_table = tables[0]
                            sample_content.append({
                                'page': page_num + 1,
                                'table_rows': len(first_table) if first_table else 0,
                                'table_cols': len(first_table[0]) if first_table and first_table[0] else 0,
                                'sample_row': first_table[0] if first_table else []
                            })
                            
                    except Exception as e:
                        result['errors'].append(f"Table extraction error on page {page_num + 1}: {str(e)}")
                    
                    # Get text for section analysis
                    try:
                        text = page.extract_text()
                        if text and ("Tax Deducted" in text or "Tax Collected" in text):
                            lines = text.split('\n')[:20]
                            sample_content.append({
                                'page': page_num + 1,
                                'type': 'text_sample', 
                                'content': [line.strip() for line in lines if line.strip()][:10]
                            })
                    except Exception as e:
                        result['errors'].append(f"Text extraction error on page {page_num + 1}: {str(e)}")
            
            result.update({
                'success': True,
                'tables_found': tables_found,
                'extraction_time': time.time() - start_time,
                'sample_content': sample_content
            })
            
        except Exception as e:
            result['errors'].append(f"pdfplumber analysis failed: {str(e)}")
            
        return result
    
    def analyze_single_pdf(self, filepath: str) -> PDFAnalysisResult:
        """Analyze a single AIS PDF file."""
        result = PDFAnalysisResult(file_path=filepath)
        
        try:
            # Basic file info
            file_stat = os.stat(filepath)
            result.file_size_mb = file_stat.st_size / (1024 * 1024)
            
            # Extract PAN from filename
            result.pan = self.extract_pan_from_filename(filepath)
            
            if not result.pan:
                result.errors.append("Could not extract PAN from filename")
                return result
            
            # Generate potential passwords
            potential_passwords = self.generate_potential_passwords(result.pan)
            
            # Try to open the PDF
            doc, working_password, tried_passwords = self.try_open_pdf(filepath, potential_passwords)
            result.tried_passwords = tried_passwords
            
            if doc is None:
                result.is_password_protected = True
                result.password_worked = False
                result.errors.append("Could not open PDF with any password")
                return result
            
            result.is_password_protected = working_password != ""
            result.password_worked = True
            result.page_count = len(doc)
            doc.close()
            
            # Analyze with PyMuPDF
            pymupdf_results = self.analyze_pymupdf(filepath, working_password)
            result.pymupdf_success = pymupdf_results['success']
            result.pymupdf_tables_found = pymupdf_results['tables_found']
            result.pymupdf_extraction_time = pymupdf_results['extraction_time']
            result.errors.extend(pymupdf_results['errors'])
            
            # Analyze with pdfplumber
            pdfplumber_results = self.analyze_pdfplumber(filepath, working_password)
            result.pdfplumber_success = pdfplumber_results['success']
            result.pdfplumber_tables_found = pdfplumber_results['tables_found']
            result.pdfplumber_extraction_time = pdfplumber_results['extraction_time']
            result.errors.extend(pdfplumber_results['errors'])
            
            # Combine sample content for analysis
            all_samples = pymupdf_results['sample_content'] + pdfplumber_results['sample_content']
            
            # Extract sections and headers
            sections_found = set()
            sample_headers = []
            
            for sample in all_samples:
                if sample.get('type') == 'text_sample':
                    content_lines = sample.get('content', [])
                    for line in content_lines:
                        line_lower = line.lower()
                        if any(keyword in line_lower for keyword in 
                               ['tax deducted', 'tax collected', 'interest', 'dividend', 'salary']):
                            sections_found.add(line)
                            if len(sample_headers) < 10:
                                sample_headers.append(line)
            
            result.sections_found = list(sections_found)
            result.sample_headers = sample_headers
            result.has_tables = result.pymupdf_tables_found > 0 or result.pdfplumber_tables_found > 0
            result.table_count = max(result.pymupdf_tables_found, result.pdfplumber_tables_found)
            
            # Store sample table structure
            if all_samples:
                result.sample_table_structure = all_samples[0]
                
        except Exception as e:
            result.errors.append(f"Analysis failed: {str(e)}")
            result.errors.append(f"Traceback: {traceback.format_exc()}")
            
        return result
    
    def find_ais_pdfs(self) -> List[str]:
        """Find all AIS PDF files in the downloads directory."""
        ais_files = []
        
        # Search pattern for AIS files
        pattern = str(self.downloads_path / "**/AY_*/*AIS-*.pdf")
        ais_files.extend(glob.glob(pattern, recursive=True))
        
        # Also check the root downloads folder
        pattern = str(self.downloads_path / "*AIS-*.pdf")
        ais_files.extend(glob.glob(pattern))
        
        return sorted(ais_files)
    
    def analyze_all_pdfs(self) -> List[PDFAnalysisResult]:
        """Analyze all AIS PDFs and return results."""
        ais_files = self.find_ais_pdfs()
        
        print(f"Found {len(ais_files)} AIS PDF files to analyze...")
        
        for i, filepath in enumerate(ais_files, 1):
            print(f"\nAnalyzing {i}/{len(ais_files)}: {Path(filepath).name}")
            
            result = self.analyze_single_pdf(filepath)
            self.results.append(result)
            
            # Print quick status
            status = "✓" if result.password_worked else "✗"
            tables = f"Tbl:{result.table_count}" if result.has_tables else "No tables"
            print(f"  {status} {result.page_count}p {result.file_size_mb:.1f}MB {tables}")
            
            if result.errors:
                print(f"    Errors: {len(result.errors)}")
        
        return self.results
    
    def generate_analysis_report(self) -> str:
        """Generate a comprehensive analysis report."""
        if not self.results:
            return "No analysis results available."
        
        report = []
        report.append("="*80)
        report.append("AIS PDF STRUCTURE ANALYSIS REPORT")
        report.append("="*80)
        report.append("")
        
        # Summary statistics
        total_files = len(self.results)
        successful_opens = sum(1 for r in self.results if r.password_worked)
        password_protected = sum(1 for r in self.results if r.is_password_protected)
        has_tables = sum(1 for r in self.results if r.has_tables)
        
        report.append("SUMMARY STATISTICS")
        report.append("-" * 40)
        report.append(f"Total AIS files analyzed: {total_files}")
        report.append(f"Successfully opened: {successful_opens} ({successful_opens/total_files*100:.1f}%)")
        report.append(f"Password protected: {password_protected} ({password_protected/total_files*100:.1f}%)")
        report.append(f"Files with tables: {has_tables} ({has_tables/total_files*100:.1f}%)")
        report.append("")
        
        # Library performance comparison
        if PYMUPDF_AVAILABLE and PDFPLUMBER_AVAILABLE:
            pymupdf_success = sum(1 for r in self.results if r.pymupdf_success)
            pdfplumber_success = sum(1 for r in self.results if r.pdfplumber_success)
            
            avg_pymupdf_time = sum(r.pymupdf_extraction_time for r in self.results if r.pymupdf_success) / max(pymupdf_success, 1)
            avg_pdfplumber_time = sum(r.pdfplumber_extraction_time for r in self.results if r.pdfplumber_success) / max(pdfplumber_success, 1)
            
            report.append("LIBRARY PERFORMANCE COMPARISON")
            report.append("-" * 40)
            report.append(f"PyMuPDF successful extractions: {pymupdf_success}/{total_files} ({pymupdf_success/total_files*100:.1f}%)")
            report.append(f"pdfplumber successful extractions: {pdfplumber_success}/{total_files} ({pdfplumber_success/total_files*100:.1f}%)")
            report.append(f"Average PyMuPDF extraction time: {avg_pymupdf_time:.3f}s")
            report.append(f"Average pdfplumber extraction time: {avg_pdfplumber_time:.3f}s")
            report.append("")
        
        # File size analysis  
        successful_results = [r for r in self.results if r.password_worked]
        if successful_results:
            sizes = [r.file_size_mb for r in successful_results]
            pages = [r.page_count for r in successful_results]
            
            report.append("FILE CHARACTERISTICS")
            report.append("-" * 40)
            report.append(f"File size range: {min(sizes):.1f}MB - {max(sizes):.1f}MB")
            report.append(f"Average file size: {sum(sizes)/len(sizes):.1f}MB")
            report.append(f"Page count range: {min(pages)} - {max(pages)} pages")
            report.append(f"Average page count: {sum(pages)/len(pages):.1f} pages")
            report.append("")
        
        # Section analysis
        all_sections = set()
        for result in successful_results:
            all_sections.update(result.sections_found)
        
        if all_sections:
            report.append("SECTIONS FOUND ACROSS ALL FILES")
            report.append("-" * 40)
            for section in sorted(all_sections):
                count = sum(1 for r in successful_results if section in r.sections_found)
                report.append(f"  {section} ({count} files)")
            report.append("")
        
        # Table structure analysis
        table_structures = []
        for result in successful_results:
            if result.sample_table_structure and 'table_rows' in result.sample_table_structure:
                table_structures.append(result.sample_table_structure)
        
        if table_structures:
            report.append("TABLE STRUCTURE PATTERNS")
            report.append("-" * 40)
            
            # Group by structure similarity
            structure_groups = {}
            for struct in table_structures:
                key = f"{struct.get('table_rows', 0)}r x {struct.get('table_cols', 0)}c"
                if key not in structure_groups:
                    structure_groups[key] = []
                structure_groups[key].append(struct)
            
            for structure, examples in structure_groups.items():
                report.append(f"  {structure}: {len(examples)} files")
                if examples[0].get('sample_row'):
                    sample_row = examples[0]['sample_row'][:3]  # First 3 columns
                    report.append(f"    Sample columns: {sample_row}")
            report.append("")
        
        # Password patterns
        password_patterns = {}
        for result in self.results:
            if result.password_worked and result.tried_passwords:
                # Find which password worked (last successful one)
                working_password = result.tried_passwords[-1] if result.tried_passwords else "unknown"
                
                # Categorize password pattern
                if working_password == result.pan:
                    pattern = "PAN_ONLY"
                elif len(working_password) == 8 and working_password.isdigit():
                    pattern = "DATE_ONLY" 
                elif len(working_password) > 10 and result.pan in working_password:
                    pattern = "DATE_PAN_COMBO"
                elif len(working_password) > 8 and working_password[-4:] == result.pan[-4:]:
                    pattern = "DATE_PAN_LAST4"
                else:
                    pattern = "OTHER"
                
                password_patterns[pattern] = password_patterns.get(pattern, 0) + 1
        
        if password_patterns:
            report.append("PASSWORD PATTERNS")
            report.append("-" * 40)
            for pattern, count in password_patterns.items():
                report.append(f"  {pattern}: {count} files")
            report.append("")
        
        # Error analysis
        error_counts = {}
        for result in self.results:
            for error in result.errors:
                # Categorize error
                if "password" in error.lower():
                    category = "PASSWORD_ERRORS"
                elif "table" in error.lower():
                    category = "TABLE_EXTRACTION_ERRORS"
                elif "text" in error.lower():
                    category = "TEXT_EXTRACTION_ERRORS"
                else:
                    category = "OTHER_ERRORS"
                
                error_counts[category] = error_counts.get(category, 0) + 1
        
        if error_counts:
            report.append("ERROR ANALYSIS")
            report.append("-" * 40)
            for category, count in error_counts.items():
                report.append(f"  {category}: {count} occurrences")
            report.append("")
        
        # Recommendations
        report.append("RECOMMENDATIONS FOR IMPLEMENTATION")
        report.append("-" * 40)
        
        if PYMUPDF_AVAILABLE and PDFPLUMBER_AVAILABLE:
            pymupdf_success = sum(1 for r in self.results if r.pymupdf_success)
            pdfplumber_success = sum(1 for r in self.results if r.pdfplumber_success)
            
            if pymupdf_success > pdfplumber_success:
                report.append("• Use PyMuPDF as primary extraction library (higher success rate)")
                report.append("• Use pdfplumber as fallback for failed extractions")
            else:
                report.append("• Use pdfplumber as primary extraction library (higher success rate)")
                report.append("• Use PyMuPDF as fallback for failed extractions")
        
        if password_patterns:
            most_common = max(password_patterns.items(), key=lambda x: x[1])
            report.append(f"• Most common password pattern: {most_common[0]} ({most_common[1]} files)")
            
        report.append("• Implement multi-password attempt strategy")
        report.append("• Handle multi-page table continuation")
        report.append("• Parse section headers for categorization")
        
        if successful_results:
            avg_tables = sum(r.table_count for r in successful_results) / len(successful_results)
            report.append(f"• Expect average of {avg_tables:.1f} tables per document")
        
        report.append("")
        
        # Individual file details (first 10 files)
        report.append("SAMPLE FILE ANALYSIS (First 10 files)")
        report.append("-" * 40)
        for i, result in enumerate(self.results[:10]):
            filename = Path(result.file_path).name
            status = "SUCCESS" if result.password_worked else "FAILED"
            report.append(f"{i+1:2d}. {filename}")
            report.append(f"     Status: {status} | Size: {result.file_size_mb:.1f}MB | Pages: {result.page_count}")
            report.append(f"     Tables: PyMuPDF={result.pymupdf_tables_found}, pdfplumber={result.pdfplumber_tables_found}")
            if result.sections_found:
                report.append(f"     Sections: {len(result.sections_found)} found")
            if result.errors:
                report.append(f"     Errors: {len(result.errors)} errors")
            report.append("")
        
        return "\n".join(report)

def main():
    """Main analysis function."""
    downloads_path = r"C:\Users\Devansh\Desktop\Taxify\downloads"
    
    print("Starting AIS PDF Structure Analysis...")
    print(f"PyMuPDF available: {PYMUPDF_AVAILABLE}")
    print(f"pdfplumber available: {PDFPLUMBER_AVAILABLE}")
    print("")
    
    if not PYMUPDF_AVAILABLE and not PDFPLUMBER_AVAILABLE:
        print("ERROR: Neither PyMuPDF nor pdfplumber is available!")
        print("Please install at least one: pip install PyMuPDF pdfplumber")
        return
    
    analyzer = AISPDFAnalyzer(downloads_path)
    results = analyzer.analyze_all_pdfs()
    
    print(f"\n\nAnalysis complete! Processed {len(results)} files.")
    
    # Generate and save report
    report = analyzer.generate_analysis_report()
    
    # Print report to console
    print("\n" + "="*80)
    print(report)
    
    # Save report to file
    report_filename = "ais_structure_analysis_report.txt"
    with open(report_filename, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\nDetailed report saved to: {report_filename}")

if __name__ == "__main__":
    main()