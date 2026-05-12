import sys
import os

# Add backend to path to import app modules
sys.path.append(os.getcwd())

from app.parsers.mbs_parser import MBSParser

file_path = r'..\data\projects\1dac5ce2-0cea-452f-9fcd-bf915390e78e\input\5a4c5ee9-ea96-48e4-9f2f-00f06d1f78b5_extracted\AnDwg-1.in'
# Adjust relative path if running from backend
if not os.path.exists(file_path):
    file_path = os.path.join('data', 'projects', '1dac5ce2-0cea-452f-9fcd-bf915390e78e', 'input', '5a4c5ee9-ea96-48e4-9f2f-00f06d1f78b5_extracted', 'AnDwg-1.in')

parser = MBSParser()
result = parser.parse(file_path)

print(f"Parser: {result['parser']}")
print(f"Confidence: {result['confidence']}")
print(f"Field count: {result['field_count']}")
for field in result['fields'][:10]:
    print(f"  {field['field_code']} ({field['field_name']}): {field['raw_value']}")
