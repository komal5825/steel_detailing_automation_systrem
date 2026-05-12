import sqlite3
import os

master_db = r'c:\Users\User\Desktop\Steel Detailing Automation\DB\master_db.db'
codes = ["F-003", "F-192", "F-047", "F-051", "F-055", "F-057", "F-059", "F-061", "F-063", "F-064", "F-065", "F-067", "F-072", "F-121", "F-122", "F-123", "F-173"]

conn = sqlite3.connect(master_db)
cur = conn.cursor()
placeholders = ','.join('?' for _ in codes)
cur.execute(f'SELECT field_code, standard_field_name FROM field_master WHERE field_code IN ({placeholders})', codes)
for row in cur.fetchall():
    print(f"{row[0]}: {row[1]}")
conn.close()
