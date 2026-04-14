import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# -------- Load processed movie data --------
df = pd.read_csv("data/processed_movies.csv")

# -------- TF-IDF Vectorization --------
tfidf = TfidfVectorizer(
    stop_words="english",
    max_features=5000
)

tfidf_matrix = tfidf.fit_transform(df["combined_features"])

# -------- Compute Cosine Similarity --------
cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)

# -------- Create index mapping --------
indices = pd.Series(df.index, index=df["title"]).drop_duplicates()

# -------- Recommendation function --------
def recommend_movies(title, top_n=10):
    if title not in indices:
        return []

    idx = indices[title]
    similarity_scores = list(enumerate(cosine_sim[idx]))

    # Sort movies by similarity score
    similarity_scores = sorted(
        similarity_scores,
        key=lambda x: x[1],
        reverse=True
    )

    # Exclude the movie itself
    similarity_scores = similarity_scores[1: top_n + 1]

    movie_indices = [i[0] for i in similarity_scores]
    return df["title"].iloc[movie_indices].tolist()


# -------- Test block --------
if __name__ == "__main__":
    test_movie = df["title"].iloc[0]
    print(f"Recommendations for '{test_movie}':")
    for movie in recommend_movies(test_movie):
        print("-", movie)
