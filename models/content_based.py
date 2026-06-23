import os
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# -------- Load processed movie data --------
DATA_PATH = os.path.join(os.path.dirname(__file__), os.pardir, "data", "processed_movies.csv")

df = pd.read_csv(DATA_PATH)

def _build_combined_features(frame):
    if "combined_features" in frame.columns:
        return frame["combined_features"].fillna("")

    pieces = []
    for column in ["genres", "keywords", "overview", "cast", "director"]:
        if column in frame.columns:
            pieces.append(frame[column].fillna(""))

    return pd.Series([" ".join(row).strip() for row in zip(*pieces)])

# Ensure combined features are present and normalized.
df["combined_features"] = _build_combined_features(df).str.lower()

tfidf = TfidfVectorizer(
    stop_words="english",
    max_features=5000,
    ngram_range=(1, 2)
)

tfidf_matrix = tfidf.fit_transform(df["combined_features"])

# Precompute cosine similarity for fast lookups.
cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)

# Map titles to indices in a case-insensitive way.
indices = pd.Series(df.index, index=df["title"].str.lower()).drop_duplicates()


def recommend_movies(title, top_n=10):
    """Return the top N content-based movie titles most similar to the given title."""
    if not title:
        return []

    key = str(title).strip().lower()
    if key not in indices:
        return []

    idx = indices[key]
    scores = list(enumerate(cosine_sim[idx]))
    scores = sorted(scores, key=lambda x: x[1], reverse=True)

    # Skip the queried movie itself.
    top_scores = scores[1: top_n + 1]
    movie_indices = [i[0] for i in top_scores]
    return df["title"].iloc[movie_indices].tolist()


def recommend_movies_with_scores(title, top_n=10):
    """Return the top N movie titles and similarity scores for a given movie."""
    if not title:
        return []

    key = str(title).strip().lower()
    if key not in indices:
        return []

    idx = indices[key]
    scores = list(enumerate(cosine_sim[idx]))
    scores = sorted(scores, key=lambda x: x[1], reverse=True)[1: top_n + 1]

    return [
        {"title": df["title"].iloc[i], "score": float(score)}
        for i, score in scores
    ]


if __name__ == "__main__":
    sample_title = df["title"].iloc[0]
    print(f"Recommendations for '{sample_title}':")
    for movie in recommend_movies(sample_title, top_n=10):
        print("-", movie)
