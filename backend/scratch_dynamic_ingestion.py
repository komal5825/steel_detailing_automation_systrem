
import os
from pathlib import Path
from app.parsers.mbs_parser import MBSParser

def run_dynamic_ingestion(project_dir):
    parser = MBSParser()
    project_path = Path(project_dir)
    
    # Find all .in files
    in_files = list(project_path.glob("**/*.in"))
    print(f"Found {len(in_files)} .in files in {project_dir}")
    
    combined_fields = {}
    
    for file_path in in_files:
        print(f"Parsing {file_path.name}...")
        try:
            result = parser.parse(str(file_path))
            for field in result['fields']:
                code = field['field_code']
                val = field['normalized_value']
                conf = field['confidence']
                
                # Simple priority: higher confidence or just overwrite if missing
                if code not in combined_fields or conf > combined_fields[code]['confidence']:
                    combined_fields[code] = {
                        'name': field['field_name'],
                        'value': val,
                        'confidence': conf,
                        'source': file_path.name
                    }
        except Exception as e:
            print(f"  Error parsing {file_path.name}: {e}")

    print("\n" + "="*60)
    print("DYNAMIC EXTRACTION RESULTS FROM PROJECT ZIP")
    print("="*60)
    print(f"| {'Code':<8} | {'Field Name':<30} | {'Value':<20} | {'Source':<15} |")
    print("|" + "-"*10 + "|" + "-"*32 + "|" + "-"*22 + "|" + "-"*17 + "|")
    
    sorted_codes = sorted(combined_fields.keys())
    for code in sorted_codes:
        f = combined_fields[code]
        print(f"| {code:<8} | {f['name']:<30} | {f['value']:<20} | {f['source']:<15} |")

if __name__ == "__main__":
    # Path to the extracted zip content for project C323-153
    project_dir = r"c:\Users\User\Desktop\Steel Detailing Automation\data\projects\1dac5ce2-0cea-452f-9fcd-bf915390e78e\input\5a4c5ee9-ea96-48e4-9f2f-00f06d1f78b5_extracted"
    run_dynamic_ingestion(project_dir)
