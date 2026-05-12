import sqlite3
import os

db_path = r'c:\Users\User\Desktop\Steel Detailing Automation\backend\app\db\steel_detailing.db'
project_id = '1dac5ce2-0cea-452f-9fcd-bf915390e78e'

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Update .in files
cur.execute('''
    UPDATE project_files 
    SET file_type = 'MBS', 
        processing_status = 'PENDING',
        classification_confidence = 90,
        file_category = 'design_file',
        likely_role = 'governing'
    WHERE project_id = ? AND original_filename LIKE '%.in'
''', (project_id,))

print(f"Updated {cur.rowcount} .in files.")

# Reset all stages for this project
cur.execute('DELETE FROM stages WHERE project_id = ?', (project_id,))
cur.execute('DELETE FROM parser_runs WHERE project_id = ?', (project_id,))
cur.execute('DELETE FROM extracted_field_values WHERE project_id = ?', (project_id,))
cur.execute('DELETE FROM validation_results WHERE project_id = ?', (project_id,))
cur.execute('DELETE FROM stage_checkpoints WHERE project_id = ?', (project_id,))
cur.execute('DELETE FROM audit_event_log WHERE project_id = ?', (project_id,))

print("Reset stages and results for the project.")

conn.commit()
conn.close()
