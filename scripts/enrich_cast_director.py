import sqlite3
import requests
import time

TMDB_API_KEY = "0c0e253b12a8c1545709407b73daecb6"
DB_PATH = "database.db"

def get_db():
    return sqlite3.connect(DB_PATH)

def fetch_cast_director(title, retries=3):
    search_url = "https://api.themoviedb.org/3/search/movie"

    for attempt in range(retries):
        try:
            res = requests.get(
                search_url,
                params={"api_key": TMDB_API_KEY, "query": title},
                timeout=10
            ).json()

            if not res.get("results"):
                return None, None

            movie_id = res["results"][0]["id"]

            credits_url = f"https://api.themoviedb.org/3/movie/{movie_id}/credits"
            credits = requests.get(
                credits_url,
                params={"api_key": TMDB_API_KEY},
                timeout=10
            ).json()

            cast = []
            director = None

            for c in credits.get("cast", [])[:5]:
                cast.append(c["name"])

            for crew in credits.get("crew", []):
                if crew["job"] == "Director":
                    director = crew["name"]
                    break

            return "|".join(cast), director

        except requests.exceptions.RequestException as e:
            print(f"⚠️ Network issue for '{title}' (attempt {attempt+1})")
            time.sleep(5)

    print(f"❌ Skipped '{title}' after retries")
    return None, None


def main():
    conn = get_db()
    cur = conn.cursor()

    # Only update movies that don't already use | format
    cur.execute("""
        SELECT movie_id, title, "cast"
        FROM movies
        WHERE "cast" NOT LIKE '%|%' OR "cast" IS NULL
    """)
    
    movies = cur.fetchall()

    print(f"Found {len(movies)} movies to update")

    for movie_id, title, existing_cast in movies:
        print(f"Updating: {title}")

        cast, director = fetch_cast_director(title)

        if cast:
            cur.execute("""
                UPDATE movies
                SET "cast"=?, director=?
                WHERE movie_id=?
            """, (cast, director, movie_id))

        time.sleep(0.25)  # avoid rate limit

    conn.commit()
    conn.close()
    print("Done updating.")

if __name__ == "__main__":
    main()
