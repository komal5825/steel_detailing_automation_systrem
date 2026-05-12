
import sys
import os
from pathlib import Path

# Add backend to path so we can import app
sys.path.append(os.getcwd())

from app.parsers.mbs_parser import MBSParser

def test_extraction(file_name):
    parser = MBSParser()
    file_path = f"c:/Users/User/Desktop/Steel Detailing Automation/data/projects/1dac5ce2-0cea-452f-9fcd-bf915390e78e/input/5a4c5ee9-ea96-48e4-9f2f-00f06d1f78b5_extracted/{file_name}"
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    print(f"\nParsing {file_name}...")
    result = parser.parse(file_path)
    
    # Target field codes we want to check
    targets = [
        "F-051", "F-059", "F-061", "F-063", "F-064", "F-065", "F-066", "F-067", 
        "F-069", "F-072", "F-073", "F-076", "F-077", "F-092", "F-093", "F-121", 
        "F-122", "F-123", "F-157", "F-159", "F-160", "F-161", "F-162", "F-163", 
        "F-173", "F-183"
    ]
    
    found = {f['field_code']: f['normalized_value'] for f in result['fields']}
    
    print("| Field Code | Value |")
    print("|---|---|")
    for t in targets:
        val = found.get(t, "MISSING")
        print(f"| {t} | {val} |")

if __name__ == "__main__":
    test_extraction("AnDwg-1.in")
    test_extraction("CompDes.in")
    test_extraction("BOM.in")
