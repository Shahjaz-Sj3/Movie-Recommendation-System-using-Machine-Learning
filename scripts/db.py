import sqlite3

conn = sqlite3.connect("database.db")
cur = conn.cursor()

cur.execute('SELECT movie_id, "cast" FROM movies')
rows = cur.fetchall()

for movie_id, cast_value in rows:
    if cast_value and "|" not in cast_value:
        words = cast_value.split()
        
        fixed = []
        i = 0
        while i < len(words):
            if i+2 < len(words) and words[i+2] == "Jr.":
                fixed.append(f"{words[i]} {words[i+1]} {words[i+2]}")
                i += 3
            else:
                fixed.append(f"{words[i]} {words[i+1]}")
                i += 2
        
        new_cast = "|".join(fixed)

        cur.execute("""
            UPDATE movies
            SET "cast"=?
            WHERE movie_id=?
        """, (new_cast, movie_id))

conn.commit()
conn.close()

print("Database cast formatting cleaned successfully.")