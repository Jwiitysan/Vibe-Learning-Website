import sqlite3
conn = sqlite3.connect(r"C:\Coding Projects\Learning App\learning.db")
c = conn.cursor()
try:
    c.execute("ALTER TABLE bubble ADD COLUMN include_in_random BOOLEAN DEFAULT 1")
    conn.commit()
    print('column added')
except Exception as e:
    print('alter error', e)
finally:
    conn.close()
