import pandas as pd
import ast
import sqlite3

# Load dataset
df = pd.read_csv("data/movies_metadata.csv")

# -------- Step 1: Keep only required columns --------
df = df[[
    "id",
    "title",
    "overview",
    "genres",
    "keywords",
    "original_language",
    "vote_average"
]]

# -------- Step 2: Handle missing values --------
df["overview"] = df["overview"].fillna("")
df["genres"] = df["genres"].fillna("[]")
df["keywords"] = df["keywords"].fillna("[]")

# -------- Step 3: Extract names from JSON-like columns --------
def extract_names(text):
    try:
        data = ast.literal_eval(text)
        return " ".join(
            [item["name"].lower().replace(" ", "") for item in data]
        )
    except:
        return ""

df["genres"] = df["genres"].apply(extract_names)
df["keywords"] = df["keywords"].apply(extract_names)



# --- fetch cast from DB ---
conn = sqlite3.connect("database.db")
cast_df = pd.read_sql("""
    SELECT m.title, c.cast, c.director
    FROM movies m
    LEFT JOIN movie_cast c ON m.movie_id = c.movie_id
""", conn)
conn.close()

df = df.merge(cast_df, on="title", how="left")

df["cast"] = df["cast"].fillna("")
df["director"] = df["director"].fillna("")

# 🔥 UPDATED combined features
df["combined_features"] = (
    df["genres"] + " " +
    df["keywords"] + " " +
    df["overview"] + " " +
    df["cast"] + " " +
    df["director"]
)

df.to_csv("data/processed_movies.csv", index=False)


# -------- Step 5: Final cleaning --------
df["combined_features"] = df["combined_features"].str.lower()

# -------- Step 6: Save processed dataset --------
df.to_csv("data/processed_movies.csv", index=False)

print("✅ PHASE 1 STEP 3 COMPLETE: processed_movies.csv created")
