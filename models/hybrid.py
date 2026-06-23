from models.content_based import recommend_movies as content_recommend
from models.collaborative import recommend_movies_cf
#from models.dl_recommender import recommend_movies_dl


def hybrid_recommendation(movie_title, user_id=None, top_n=10):

    # Get results
    content_results = content_recommend(movie_title, top_n=top_n * 2)
    dl_results = []
    if user_id:
        cf_results = recommend_movies_cf(user_id, top_n=top_n)
    else:
        cf_results = []

    scores = {}
    appearance_count = {}

    def add_score(movies, weight):
        for rank, movie in enumerate(movies):
            base_score = weight * (1 / (rank + 1))

            scores[movie] = scores.get(movie, 0) + base_score
            appearance_count[movie] = appearance_count.get(movie, 0) + 1

    # 🎯 Adjusted weights
    add_score(content_results, 0.35)
    add_score(dl_results, 0.35)
    add_score(cf_results, 0.30)

    # 🔥 Boost movies that appear in multiple models
    for movie in scores:
        if appearance_count[movie] > 1:
            scores[movie] += 0.1 * appearance_count[movie]

    # Final ranking
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    return ranked[:top_n]