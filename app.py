from flask import Flask, request, render_template, redirect, session, jsonify
import sqlite3
import hashlib
import pandas as pd
import requests
import os
from dotenv import load_dotenv



from models.content_based import recommend_movies as content_recommend
from models.hybrid import hybrid_recommendation


load_dotenv()

app = Flask(__name__)
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
app.secret_key = os.getenv("SECRET_KEY")

print("Loading movie dataset into memory...")
MOVIES_DF = pd.read_csv("data/processed_movies.csv")
print("Dataset loaded.")

# ---------------- DATABASE HELPER ----------------
def get_db():
    return sqlite3.connect("database.db")


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            user_id INTEGER,
            movie_id INTEGER,
            PRIMARY KEY (user_id, movie_id)
        )
    """)
    conn.commit()
    conn.close()


init_db()


# ---------------- MOVIE HELPERS ----------------
def get_movie_id(title):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT movie_id FROM movies WHERE title=?", (title,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def get_movie_title(movie_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT title FROM movies WHERE movie_id=?", (movie_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def is_in_watchlist(user_id, movie_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM watchlist WHERE user_id=? AND movie_id=?",
        (user_id, movie_id)
    )
    result = cur.fetchone()
    conn.close()
    return result is not None


def get_watchlist_titles(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT m.movie_id, m.title FROM watchlist w JOIN movies m ON w.movie_id = m.movie_id WHERE w.user_id = ?",
        (user_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def is_watched(user_id, movie_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM watched_movies WHERE user_id=? AND movie_id=?",
        (user_id, movie_id)
    )
    result = cur.fetchone()
    conn.close()
    return result is not None


# ---------------- SEED MOVIE (FIXED) ----------------
def get_user_seed_movie(user_id):
    conn = get_db()
    cur = conn.cursor()

    # 1️⃣ Highest rated movie
    cur.execute("""
        SELECT m.title
        FROM ratings r
        JOIN movies m ON r.movie_id = m.movie_id
        WHERE r.user_id = ?
        ORDER BY r.rating DESC
        LIMIT 1
    """, (user_id,))
    row = cur.fetchone()

    if row:
        conn.close()
        return row[0]

    # 2️⃣ Fallback: most recently watched (NO rowid bug)
    cur.execute("""
        SELECT m.title
        FROM watched_movies w
        JOIN movies m ON w.movie_id = m.movie_id
        WHERE w.user_id = ?
        ORDER BY w.movie_id DESC
        LIMIT 1
    """, (user_id,))
    row = cur.fetchone()

    conn.close()
    return row[0] if row else None


# ---------------- TASTE SUMMARY ----------------
def get_user_taste_summary(user_id):
    df = MOVIES_DF

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT m.title
        FROM watched_movies w
        JOIN movies m ON w.movie_id = m.movie_id
        WHERE w.user_id=?
    """, (user_id,))
    watched_titles = [r[0] for r in cur.fetchall()]
    conn.close()

    watched_df = df[df["title"].isin(watched_titles)]

    genre_count = {}
    actor_count = {}
    director_count = {}

    # ===== GENRES (space separated in your dataset) =====
    if "genres" in watched_df.columns:
        for g in watched_df["genres"].dropna():
            for genre in str(g).split():   # SPACE split
                genre = genre.strip().replace("sciencefiction", "Sci Fi").title()
                genre_count[genre] = genre_count.get(genre, 0) + 1

       # ===== ACTORS =====
    if "cast" in watched_df.columns:
        for c in watched_df["cast"].dropna():
            actors = str(c).split("|")

            for actor in actors:
                actor = actor.strip()
                if actor and actor.lower() != "nan":
                    actor_count[actor] = actor_count.get(actor, 0) + 1


    # ===== DIRECTORS =====
    if "director" in watched_df.columns:
        for d in watched_df["director"].dropna():
            directors = str(d).split("|")

            for director in directors:
                director = director.strip()
                if director and director.lower() != "nan":
                    director_count[director] = director_count.get(director, 0) + 1

    return {
    "genres": sorted(genre_count, key=genre_count.get, reverse=True)[:3],
    "genre_counts": [
        genre_count[g]
        for g in sorted(genre_count, key=genre_count.get, reverse=True)[:3]
    ],
    "actors": sorted(actor_count, key=actor_count.get, reverse=True)[:3],
    "directors": sorted(director_count, key=director_count.get, reverse=True)[:2],
}


def get_all_watched_titles(user_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT m.title
        FROM watched_movies w
        JOIN movies m ON w.movie_id = m.movie_id
        WHERE w.user_id = ?
    """, (user_id,))

    titles = [row[0] for row in cur.fetchall()]
    conn.close()
    return titles

# ---------------- HOME ----------------
@app.route("/")
def home():
    user_id = session.get("user_id")
    recommendations = []

    if not user_id:
        return render_template(
            "index.html",
            logged_in=False,
            active_page="home",
            seed_movie=None,
            for_you=[]
        )

    watched_titles = get_all_watched_titles(user_id)

    if not watched_titles:
        return render_template(
            "index.html",
            logged_in=True,
            active_page="home",
            seed_movie=None,
            for_you=[]
        )

    # ===== Aggregate hybrid scores =====
    combined_scores = {}

    for watched in watched_titles:
        raw_recs = hybrid_recommendation(
            movie_title=watched,
            user_id=user_id,
            top_n=20
        )

        for title, score in raw_recs:
            if title in watched_titles:
                continue

            combined_scores[title] = combined_scores.get(title, 0) + score

    # ===== Rank globally =====
    ranked = sorted(
        combined_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    if not ranked:
        return render_template(
            "index.html",
            logged_in=True,
            active_page="home",
            seed_movie=None,
            for_you=[]
        )

    max_score = ranked[0][1]

    for title, score in ranked[:10]:
        movie_id = get_movie_id(title)
        if not movie_id:
            continue

        confidence = round((score / max_score) * 100, 1)

        recommendations.append({
    "title": title,
    "poster": get_movie_poster(title),
    "movie_id": movie_id,
    "avg_rating": get_average_rating(movie_id),
    "confidence": confidence,
    "reason": "Based on your watching history",
    "watched": is_watched(user_id, movie_id)
})

    return render_template(
        "index.html",
        logged_in=True,
        active_page="home",
        seed_movie=None,
        for_you=recommendations
    )





# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = hashlib.sha256(request.form["password"].encode()).hexdigest()

        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, password)
            )
            conn.commit()
            conn.close()
            return redirect("/login")
        except:
            return "Username already exists"

    return render_template("register.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = hashlib.sha256(request.form["password"].encode()).hexdigest()

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id FROM users WHERE username=? AND password=?",
            (username, password)
        )
        user = cur.fetchone()
        conn.close()

        if user:
            session["user_id"] = user[0]
            session["username"] = username
            return redirect("/")
        return "Invalid credentials"

    return render_template("login.html")


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------- DISCOVER ----------------
@app.route("/discover")
def discover():
    category = request.args.get("category")
    value = request.args.get("value")
    user_id = session.get("user_id")

    df = MOVIES_DF
    results = []

    if category == "genres" and value and "combined_features" in df.columns:
        filtered = df[
            df["combined_features"]
            .str.lower()
            .str.contains(value.lower(), na=False)
        ]

        for title in filtered["title"].head(20):
            movie_id = get_movie_id(title)
            results.append({
                "title": title,
                "poster": get_movie_poster(title),
                "movie_id": movie_id,
                "watched": is_watched(user_id, movie_id) if user_id else False
            })

    return render_template(
        "discover.html",
        results=results,
        category=category,
        value=value,
        logged_in=("user_id" in session),
        active_page="discover"
    )


# ---------------- RECOMMEND UI ----------------
@app.route("/recommend_ui")
def recommend_ui():
    movie_title = request.args.get("movie")
    if not movie_title:
        return redirect("/")

    mode = request.args.get("mode", "hybrid")
    user_id = session.get("user_id")

    if mode == "content":
        raw_recs = content_recommend(movie_title, top_n=30)
    else:
        raw_recs = hybrid_recommendation(
            movie_title=movie_title,
            user_id=user_id,
            top_n=30
        )

    recommendations = []
    count = 0

    for item in raw_recs:
        title = item[0] if isinstance(item, tuple) else item
        movie_id = get_movie_id(title)
        if not movie_id:
            continue

        if user_id and is_watched(user_id, movie_id):
            continue

        recommendations.append({
            "title": title,
            "poster": get_movie_poster(title),
            "movie_id": movie_id,
            "avg_rating": get_average_rating(movie_id),
            "watchlist": is_in_watchlist(user_id, movie_id) if user_id else False
        })

        count += 1
        if count == 10:
            break

    return render_template(
        "results.html",
        movie=movie_title,
        recommendations=recommendations,
        logged_in=("user_id" in session),
        mode=mode
    )




# ---------------- MARK WATCHED ----------------
@app.route("/mark_watched", methods=["POST"])
def mark_watched():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    movie_id = request.form["movie_id"]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO watched_movies (user_id, movie_id)
        VALUES (?, ?)
    """, (user_id, movie_id))
    conn.commit()
    conn.close()

    return redirect(request.referrer or "/")


# ---------------- WATCHLIST ----------------
@app.route("/watchlist")
def watchlist():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    watchlist_rows = get_watchlist_titles(user_id)
    movies = []

    for movie_id, title in watchlist_rows:
        movies.append({
            "movie_id": movie_id,
            "title": title,
            "poster": get_movie_poster(title),
            "avg_rating": get_average_rating(movie_id),
            "watched": is_watched(user_id, movie_id),
            "watchlist": True
        })

    return render_template(
        "watchlist.html",
        movies=movies,
        logged_in=True,
        active_page="watchlist"
    )


@app.route("/add_to_watchlist", methods=["POST"])
def add_to_watchlist():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    movie_id = request.form["movie_id"]

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO watchlist (user_id, movie_id) VALUES (?, ?)",
        (user_id, movie_id)
    )
    conn.commit()
    conn.close()

    return redirect(request.referrer or "/")


@app.route("/remove_from_watchlist", methods=["POST"])
def remove_from_watchlist():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    movie_id = request.form["movie_id"]

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM watchlist WHERE user_id=? AND movie_id=?",
        (user_id, movie_id)
    )
    conn.commit()
    conn.close()

    return redirect(request.referrer or "/")






# #-----RATE--------


# @app.route("/rate", methods=["POST"])
# def rate_movie():
#     if "user_id" not in session:
#         return redirect("/login")

#     user_id = session["user_id"]
#     movie_id = request.form["movie_id"]
#     rating = int(request.form["rating"])

#     conn = get_db()
#     cur = conn.cursor()

#     cur.execute("""
#         INSERT OR REPLACE INTO ratings (user_id, movie_id, rating)
#         VALUES (?, ?, ?)
#     """, (user_id, movie_id, rating))

#     # ensure watched
#     cur.execute("""
#         INSERT OR IGNORE INTO watched_movies (user_id, movie_id)
#         VALUES (?, ?)
#     """, (user_id, movie_id))

#     conn.commit()
#     conn.close()

#     return redirect(request.referrer or "/")



# # ---------------- REVIEW ----------------
# @app.route("/review", methods=["POST"])
# def add_review():
#     if "user_id" not in session:
#         return redirect("/login")

#     conn = get_db()
#     cur = conn.cursor()

#     cur.execute("""
#         INSERT OR REPLACE INTO reviews (user_id, movie_id, review)
#         VALUES (?, ?, ?)
#     """, (
#         session["user_id"],
#         request.form["movie_id"],
#         request.form["review"]
#     ))

#     conn.commit()
#     conn.close()

#     return redirect(request.referrer or "/")



# ---------------- has rated or reviewed ----------------


def has_rated_or_reviewed(user_id, movie_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT 1 FROM ratings
        WHERE user_id=? AND movie_id=?
    """, (user_id, movie_id))
    rated = cur.fetchone()

    cur.execute("""
        SELECT 1 FROM reviews
        WHERE user_id=? AND movie_id=?
    """, (user_id, movie_id))
    reviewed = cur.fetchone()

    conn.close()
    return rated or reviewed


def get_average_rating(movie_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT AVG(rating)
        FROM ratings
        WHERE movie_id=?
    """, (movie_id,))

    avg = cur.fetchone()[0]
    conn.close()

    return round(avg, 1) if avg else None




# ---------------- PROFILE ----------------
@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    conn = get_db()
    cur = conn.cursor()

    # Watched
    cur.execute("""
        SELECT m.title
        FROM watched_movies w
        JOIN movies m ON w.movie_id = m.movie_id
        WHERE w.user_id=?
    """, (user_id,))
    watched = [r[0] for r in cur.fetchall()]

    # Rated
    cur.execute("""
        SELECT m.title, r.rating
        FROM ratings r
        JOIN movies m ON r.movie_id = m.movie_id
        WHERE r.user_id=?
    """, (user_id,))
    rated = cur.fetchall()

    # Reviewed
    cur.execute("""
        SELECT m.title, rv.review
        FROM reviews rv
        JOIN movies m ON rv.movie_id = m.movie_id
        WHERE rv.user_id=?
    """, (user_id,))
    reviewed = cur.fetchall()

    conn.close()

    taste = get_user_taste_summary(user_id)

    return render_template(
        "profile.html",
        watched=watched,
        rated=rated,
        reviewed=reviewed,
        ratings_count=len(rated),
        reviews_count=len(reviewed),
        watched_count=len(watched),
        taste=taste
    )
#-----POP-UP------

@app.route("/rate_and_review", methods=["POST"])
def rate_and_review():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    movie_title = request.form["movie_id"]

    movie_id = get_movie_id(movie_title)
    rating = int(request.form["rating"])
    review = request.form.get("review", "").strip()

    conn = get_db()
    cur = conn.cursor()

    # Save rating
    cur.execute("""
        INSERT OR REPLACE INTO ratings (user_id, movie_id, rating)
        VALUES (?, ?, ?)
    """, (user_id, movie_id, rating))

    # Save review
    if review:
        cur.execute("""
            INSERT OR REPLACE INTO reviews (user_id, movie_id, review)
            VALUES (?, ?, ?)
        """, (user_id, movie_id, review))

    conn.commit()
    conn.close()

    return redirect("/profile")






# ---------------- AUTOCOMPLETE ----------------
@app.route("/autocomplete")
def autocomplete():
    q = request.args.get("q", "").lower()
    if not q:
        return jsonify([])

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT title FROM movies
        WHERE LOWER(title) LIKE ?
        LIMIT 10
    """, (f"{q}%",))
    results = [r[0] for r in cur.fetchall()]
    conn.close()
    return jsonify(results)


# ---------------- POSTER (CACHED) ----------------

import requests
import urllib.parse
import sqlite3

TMDB_API_KEY = os.getenv("TMDB_API_KEY")


def get_movie_poster(title):
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    try:
        # 1️⃣ CHECK DATABASE FIRST (FAST)
        cur.execute("SELECT poster_url FROM movies WHERE title=?", (title,))
        result = cur.fetchone()

        if result and result[0]:
            return result[0]

        # 2️⃣ FETCH FROM TMDB (ONLY IF NULL)
        encoded_title = urllib.parse.quote(title)

        search_url = (
            f"https://api.themoviedb.org/3/search/movie"
            f"?api_key={TMDB_API_KEY}&query={encoded_title}&include_adult=false"
        )

        response = requests.get(search_url, timeout=5)
        data = response.json()

        if data.get("results"):
            # 3️⃣ LOOP THROUGH RESULTS UNTIL POSTER FOUND
            for movie in data["results"]:
                poster_path = movie.get("poster_path")

                if poster_path:
                    full_url = f"https://image.tmdb.org/t/p/w500{poster_path}"

                    # 4️⃣ SAVE TO DATABASE (CACHE)
                    cur.execute(
                        "UPDATE movies SET poster_url=? WHERE title=?",
                        (full_url, title)
                    )
                    conn.commit()

                    return full_url

    except Exception as e:
        print(f"TMDB Error for {title}: ", e)

    finally:
        conn.close()

    # 5️⃣ FALLBACK IMAGE
    return "/static/images/default_poster.jpg"

# ---------------- API ----------------
@app.route("/recommend")
def recommend_api():
    return jsonify(hybrid_recommendation(request.args.get("movie")))


@app.route("/recommend_content")
def recommend_content_api():
    movie_title = request.args.get("movie")
    if not movie_title:
        return jsonify([])

    recommendations = content_recommend(movie_title, top_n=10)
    return jsonify(recommendations)


# ---------------- RUN ----------------

if __name__ == "__main__":
    app.run(debug=True)







