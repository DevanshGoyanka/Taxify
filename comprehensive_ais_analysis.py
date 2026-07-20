"""
Comprehensive AIS PDF Analysis
==============================

This script analyzes all AIS PDFs to understand their structure and create
the optimal extraction strategy. Uses the working password pattern:
lowercase_pan + DDMMYYYY
"""

import os
import glob
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Set
import json

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    print("pdfplumber not available")
    exit(1)

@dataclass
class AISAnalysisResult:
    """Complete analysis results for an AIS PDF."""
    file_path: str
    pan: str
    name: str = ""
    file_size_mb: float = 0.0
    page_count: int = 0
    
    # Password info
    working_password: str = ""
    password_attempts: int = 0
    
    # Content analysis
    tables_per_page: List[int] = field(default_factory=list)
    total_tables: int = 0
    sections_found: Set[str] = field(default_factory=set)
    
    # Sample data
    first_page_text: str = ""
    sample_table_headers: List[str] = field(default_factory=list)
    sample_table_row: List[str] = field(default_factory=list)
    
    # Structure patterns
    multi_page_tables: bool = False
    table_structures: List[Dict] = field(default_factory=list)
    
    # Extraction quality  
    extraction_success: bool = False
    errors: List[str] = field(default_factory=list)

class ComprehensiveAISAnalyzer:
    """Analyze all AIS PDFs comprehensively."""
    
    def __init__(self, downloads_path: str):
        self.downloads_path = Path(downloads_path)
        self.results: List[AISAnalysisResult] = []
        
        # Client data with actual DOBs
        self.client_data = {
            "CDGPP3326R": "07-Feb-89", "BIQPT8609H": "01-Jan-65", "AIWPA6115G": "09-Nov-76",
            "ASIPD7661E": "15-Jan-67", "AHLPU2662E": "10-Jul-75", "AODPR7988H": "06-Jun-84",
            "BDQPK0363J": "17-Mar-75", "DBPPS5425A": "20-Apr-58", "AQRPD8621M": "04-Aug-89",
            "AKXPI1815N": "12-Sep-96", "AMIPR1349D": "18-Dec-84", "ASHPM1179M": "18-Mar-74",
            "ACJPK1346G": "16-Oct-62", "BJZPM5736N": "12-Sep-75", "AODPT6977Q": "11-Oct-88",
            "DSAPS5307B": "05-Sep-89", "AOQPR3128E": "09-Jul-77", "ARMPG2124J": "01-Jan-85",
            "AAPPW0842B": "21-Mar-75", "ADHPT8265E": "01-Jan-68", "CTQPK9322N": "25-Dec-76",
            "AAOPI1287K": "02-Dec-68", "AXKPM0717F": "20-Aug-55", "ANBPG6588M": "17-Dec-84",
            "DDSPK6942K": "25-Jan-77", "ALIPD2666E": "04-Jun-65", "LNHPS6734G