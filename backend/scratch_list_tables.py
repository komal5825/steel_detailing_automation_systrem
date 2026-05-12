
import sqlite3

db_path = r'c:\Users\User\Desktop\Steel Detailing Automation\DB\master_db.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Tables in master_db.db:")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
for table in tables:
    print(f"- {table[0]}")
    # Also print columns for project_fields or similar
    if "field" in table[0].lower():
        cursor.execute(f"PRAGMA table_info({table[0]})")
        cols = cursor.fetchall()
        print(f"  Columns: {[c[1] for c in cols]}")

conn.close()
