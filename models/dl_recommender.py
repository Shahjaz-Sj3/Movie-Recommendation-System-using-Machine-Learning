import pickle
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

# Load data
df = pd.read_csv("data/processed_movies.csv")

# Load embeddings & indices
with open("models/movie_embeddings.pkl", "rb") as f:
    embeddings = pickle.load(f)

indices = pd.read_pickle("models/movie_indices.pkl")

# Precompute similarity
similarity_matrix = cosine_similarity(embeddings)

def recommend_movies_dl(title, top_n=10):
    if title not in indices:
        return []

    idx = indices[title]
    scores = list(enumerate(similarity_matrix[idx]))
    scores = sorted(scores, key=lambda x: x[1], reverse=True)
    scores = scores[1:top_n+1]

    movie_indices = [i[0] for i in scores]
    return df["title"].iloc[movie_indices].tolist()
