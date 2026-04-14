import pandas as pd
import torch
import pickle
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Load dataset
df = pd.read_csv("data/processed_movies.csv")

# Device
device = "cuda" if torch.cuda.is_available() else "cpu"
print("Using device:", device)

# Load model
model = SentenceTransformer("all-MiniLM-L6-v2", device=device)

# Encode
embeddings = model.encode(
    df["combined_features"].tolist(),
    batch_size=64,
    show_progress_bar=True
)

# Save embeddings
with open("models/movie_embeddings.pkl", "wb") as f:
    pickle.dump(embeddings, f)

# Save index mapping
indices = pd.Series(df.index, index=df["title"]).drop_duplicates()
indices.to_pickle("models/movie_indices.pkl")

print("DL embeddings saved successfully")
