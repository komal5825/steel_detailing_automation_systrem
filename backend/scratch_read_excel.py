
import pandas as pd
import os

file_path = r'c:\Users\User\Desktop\Steel Detailing Automation\Outputs for Steel Deatailig Automation\6 May 2026\FILED DICT.xlsx'

if not os.path.exists(file_path):
    print(f"File not found: {file_path}")
    exit(1)

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', None)

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

df = pd.read_excel(file_path)
print("Columns:", df.columns.tolist())
print("-" * 40)
# Adjust column names based on the "Columns" printout if necessary
# For now, let's just print the whole thing but formatted better
print(df)
