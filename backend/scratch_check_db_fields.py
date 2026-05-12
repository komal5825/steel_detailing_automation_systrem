import sqlite3
db_path = r'c:\Users\User\Desktop\Steel Detailing Automation\backend\app\db\steel_detailing.db'
project_id = '1dac5ce2-0cea-452f-9fcd-bf915390e78e'
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT field_code, raw_value, source_path FROM extracted_field_values WHERE project_id = ? AND field_code IN ('F-192', 'F-055', 'F-054', 'F-057', 'F-003', 'F-047')", (project_id,))
for row in cur.fetchall():
    print(f"{row[0]}: {row[1]} (from {row[2]})")
conn.close()
