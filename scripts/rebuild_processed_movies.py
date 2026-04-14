import sqlite3
import pandas as pd

# 1️⃣ Load existing processed CSV
base_df = pd.read_csv("data/processed_movies.csv")

# 2️⃣ Load cast & director from database
conn = sqlite3.connect("database.db")
db_df = pd.read_sql("""
    SELECT
        title,
        "cast",
        director
    FROM movies
""", conn)
conn.close()

# 3️⃣ Merge safely (avoid column collision)
df = base_df.merge(
    db_df,
    on="title",
    how="left",
    suffixes=("", "_db")
)

# 4️⃣ Replace old cast/director with DB values if available
if "cast_db" in df.columns:
    df["cast"] = df["cast_db"]
    df.drop(columns=["cast_db"], inplace=True)

if "director_db" in df.columns:
    df["director"] = df["director_db"]
    df.drop(columns=["director_db"], inplace=True)

# 5️⃣ Rebuild combined_features safely
df["combined_features"] = (
    df.get("genres", "").fillna("") + " " +
    df.get("overview", "").fillna("") + " " +
    df.get("cast", "").fillna("") + " " +
    df.get("director", "").fillna("")
)

# 6️⃣ Save updated CSV
df.to_csv("data/processed_movies.csv", index=False)

print("✅ processed_movies.csv rebuilt successfully with cast & director")