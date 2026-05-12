
import sqlite3

db_path = r'c:\Users\User\Desktop\Steel Detailing Automation\DB\master_db.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

codes = ('F-035', 'F-132', 'F-133', 'F-143', 'F-148')
query = f"SELECT field_code, standard_field_name, description FROM field_master WHERE field_code IN {codes}"
cursor.execute(query)
rows = cursor.fetchall()
for row in rows:
    print(f"{row[0]}: {row[1]} - {row[2]}")

conn.close()
