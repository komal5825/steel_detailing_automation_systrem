
import sqlite3

db_path = r'c:\Users\User\Desktop\Steel Detailing Automation\DB\master_db.db'
project_id = '1dac5ce2-0cea-452f-9fcd-bf915390e78e'

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print(f"Checking field_values for project {project_id}:")
cursor.execute("SELECT field_code, normalized_value FROM field_values WHERE project_id = ?", (project_id,))
rows = cursor.fetchall()
for row in rows:
    print(f"{row[0]}: {row[1]}")

conn.close()
