import sqlite3
import os

db_path = r'c:\Users\User\Desktop\Steel Detailing Automation\backend\app\db\steel_detailing.db'
project_id = '1dac5ce2-0cea-452f-9fcd-bf915390e78e'

conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute('SELECT stored_path, original_filename FROM project_files WHERE project_id = ? AND original_filename = ?', (project_id, 'AnDwg-1.in'))
row = cur.fetchone()
if row:
    print(f"Path: {row[0]}")
    print(f"Exists: {os.path.exists(row[0])}")
else:
    print("Not found")
conn.close()
