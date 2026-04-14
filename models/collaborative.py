import sqlite3
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

# -------- Load ratings from database --------
def load_ratings():
    conn = sqlite3.connect("database.db")
    df = pd.read_sql_query(
        "SELECT user_id, movie_id, rating FROM ratings",
        conn
    )
    conn.close()
    return df

# -------- Build item-item similarity --------
def build_item_similarity():
    ratings_df = load_ratings()

    # If no ratings yet, return None
    if ratings_df.empty:
        return None, None

    # Create user-movie rating matrix
    rating_matrix = ratings_df.pivot_table(
        index="movie_id",
        columns="user_id",
        values="rating"
    ).fillna(0)

    # Compute cosine similarity between movies
    similarity_matrix = cosine_similarity(rating_matrix)

    similarity_df = pd.DataFrame(
        similarity_matrix,
        index=rating_matrix.index,
        columns=rating_matrix.index
    )

    return similarity_df, rating_matrix.index

# -------- Recommendation function --------
def recommend_movies_cf(movie_id, top_n=10):
    similarity_df, movie_ids = build_item_similarity()

    if similarity_df is None or movie_id not in similarity_df.index:
        return []

    similar_scores = similarity_df[movie_id].sort_values(ascending=False)

    # Exclude the movie itself
    similar_movies = similar_scores.iloc[1:top_n + 1].index.tolist()

    return similar_movies


# -------- Test block --------
if __name__ == "__main__":
    print("Collaborative filtering module loaded.")
