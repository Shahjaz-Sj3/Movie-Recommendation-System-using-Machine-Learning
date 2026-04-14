import sqlite3

conn = sqlite3.connect("database.db")
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE movies ADD COLUMN poster_url TEXT;")
    print("✅ poster_url column added successfully")
except Exception as e:
    print("⚠️", e)

conn.commit()
conn.close()
