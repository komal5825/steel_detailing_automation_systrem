import sqlite3
master_db = r'c:\Users\User\Desktop\Steel Detailing Automation\DB\master_db.db'
conn = sqlite3.connect(master_db)
cur = conn.cursor()
cur.execute("SELECT field_code, standard_field_name, legacy_aliases FROM field_master WHERE field_code IN ('F-054', 'F-055', 'F-192')")
for row in cur.fetchall():
    print(f"{row[0]}: {row[1]} (Aliases: {row[2]})")
conn.close()
