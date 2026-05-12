
import sqlite3

db_path = r'c:\Users\User\Desktop\Steel Detailing Automation\DB\master_db.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(field_master)")
cols = cursor.fetchall()
for col in cols:
    print(f"{col[1]} ({col[2]})")

conn.close()
