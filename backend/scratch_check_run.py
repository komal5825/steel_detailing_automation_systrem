import sqlite3
db_path = r'c:\Users\User\Desktop\Steel Detailing Automation\backend\app\db\steel_detailing.db'
project_id = '1dac5ce2-0cea-452f-9fcd-bf915390e78e'
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute('SELECT pf.original_filename, pr.status, pr.message FROM parser_runs pr JOIN project_files pf ON pr.project_file_id = pf.id WHERE pr.project_id = ? AND pf.original_filename = ?', (project_id, 'AnDwg-1.in'))
print(cur.fetchone())
conn.close()
