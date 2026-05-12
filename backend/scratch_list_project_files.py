
import sqlite3
import os

db_path = r'c:\Users\User\Desktop\Steel Detailing Automation\backend\app\db\steel_detailing.db'
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT id, proposal_id, name FROM projects")
projects = cur.fetchall()

for proj in projects:
    print(f"Project: {proj['name']} ({proj['proposal_id']}) ID: {proj['id']}")
    cur.execute("SELECT original_filename, stored_path, likely_role FROM project_files WHERE project_id = ?", (proj['id'],))
    files = cur.fetchall()
    for f in files:
        print(f"  - {f['original_filename']} -> {f['stored_path']} ({f['likely_role']})")
    print("-" * 40)

conn.close()
