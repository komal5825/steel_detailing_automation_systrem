import sqlite3
db_path = r'c:\Users\User\Desktop\Steel Detailing Automation\backend\app\db\steel_detailing.db'
project_id = '1dac5ce2-0cea-452f-9fcd-bf915390e78e'
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute('''
    SELECT efv.field_code, efv.field_name, efv.raw_value 
    FROM extracted_field_values efv
    JOIN project_files pf ON efv.project_file_id = pf.id
    WHERE efv.project_id = ? AND pf.original_filename = ?
''', (project_id, 'AnDwg-1.in'))
for row in cur.fetchall():
    print(f"{row[0]}: {row[1]} = {row[2]}")
conn.close()
