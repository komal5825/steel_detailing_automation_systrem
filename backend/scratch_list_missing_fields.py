
import sqlite3
import os

codes = [
    "F-051", "F-059", "F-061", "F-063", "F-064", "F-065", "F-066", "F-067", "F-069", 
    "F-072", "F-073", "F-076", "F-077", "F-092", "F-093", "F-095", "F-098", "F-100", 
    "F-104", "F-107", "F-108", "F-109", "F-111", "F-112", "F-114", "F-115", "F-116", 
    "F-118", "F-119", "F-121", "F-122", "F-123", "F-124", "F-149", "F-150", "F-157", 
    "F-159", "F-160", "F-161", "F-162", "F-163", "F-170", "F-173", "F-183"
]

db_path = "c:/Users/User/Desktop/Steel Detailing Automation/DB/master_db.db"

if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

placeholders = ','.join(['?'] * len(codes))
query = f"SELECT field_code, standard_field_name, description FROM field_master WHERE field_code IN ({placeholders})"

cur.execute(query, codes)
rows = cur.fetchall()

print("| Field Code | Name | Description |")
print("|---|---|---|")
for row in rows:
    print(f"| {row['field_code']} | {row['standard_field_name']} | {row['description']} |")

conn.close()
