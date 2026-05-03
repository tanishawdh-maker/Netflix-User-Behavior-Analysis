import csv
import random
from datetime import date, datetime, timedelta
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
RANDOM_SEED = 42

COUNTRIES = [
    "United States",
    "India",
    "United Kingdom",
    "Canada",
    "Brazil",
    "Germany",
    "France",
    "Japan",
    "South Korea",
    "Mexico",
    "Australia",
    "Spain",
]

GENRES = [
    "Drama",
    "Comedy",
    "Thriller",
    "Romance",
    "Action",
    "Documentary",
    "Sci-Fi",
    "Horror",
    "Crime",
    "Animation",
]

TITLE_WORDS = [
    "Midnight",
    "Legacy",
    "Signal",
    "Empire",
    "Frontier",
    "Archive",
    "Pulse",
    "Horizon",
    "Voyage",
    "Kingdom",
    "Witness",
    "Circuit",
]

TITLE_SUFFIXES = [
    "Stories",
    "Diaries",
    "Files",
    "Road",
    "Season",
    "Protocol",
    "Dreams",
    "City",
    "House",
    "Run",
]


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def weighted_choice(values, weights):
    return random.choices(values, weights=weights, k=1)[0]


def generate_users(user_count=550):
    country_weights = [32, 15, 9, 8, 7, 5, 5, 4, 4, 5, 3, 3]
    return [
        {
            "user_id": user_id,
            "age": random.randint(16, 70),
            "country": weighted_choice(COUNTRIES, country_weights),
        }
        for user_id in range(1, user_count + 1)
    ]


def generate_shows(show_count=350):
    genre_weights = [17, 14, 11, 9, 11, 10, 8, 7, 7, 6]
    shows = []
    used_titles = set()

    for show_id in range(1, show_count + 1):
        title = f"{random.choice(TITLE_WORDS)} {random.choice(TITLE_SUFFIXES)}"
        if title in used_titles:
            title = f"{title} {show_id}"
        used_titles.add(title)

        shows.append(
            {
                "show_id": show_id,
                "title": title,
                "genre": weighted_choice(GENRES, genre_weights),
                "release_year": random.randint(1990, 2025),
            }
        )

    return shows


def build_user_preferences(users):
    preferences = {}
    for user in users:
        favorite_genres = random.sample(GENRES, 3)
        other_genres = [genre for genre in GENRES if genre not in favorite_genres]
        preferences[user["user_id"]] = {
            "genres": favorite_genres + other_genres,
            "weights": [10, 7, 5] + [1] * len(other_genres),
            "favorites": set(favorite_genres),
        }
    return preferences


def generate_watch_history(users, shows, row_count=15000):
    shows_by_genre = {}
    for show in shows:
        shows_by_genre.setdefault(show["genre"], []).append(show)

    preferences = build_user_preferences(users)
    start_date = date(2024, 1, 1)
    end_date = date(2025, 12, 31)
    days_between = (end_date - start_date).days
    heavy_users = set(random.sample([user["user_id"] for user in users], 80))

    history = []
    watch_id = 1

    while watch_id <= row_count:
        user = random.choice(users)
        pref = preferences[user["user_id"]]
        sessions_today = 1

        if user["user_id"] in heavy_users and random.random() < 0.35:
            sessions_today = random.randint(3, 6)
        elif random.random() < 0.14:
            sessions_today = random.randint(2, 4)

        base_date = start_date + timedelta(days=random.randint(0, days_between))
        base_time = datetime.combine(base_date, datetime.min.time()) + timedelta(
            hours=random.randint(16, 23),
            minutes=random.randint(0, 59),
        )

        for session_index in range(sessions_today):
            if watch_id > row_count:
                break

            genre = weighted_choice(pref["genres"], pref["weights"])
            show = random.choice(shows_by_genre[genre])
            watch_time = base_time + timedelta(minutes=session_index * random.randint(35, 95))
            watch_duration = random.randint(70, 165) if random.random() < 0.74 else random.randint(15, 69)

            rating_weights = [1, 2, 4, 6, 8] if genre in pref["favorites"] else [4, 5, 5, 3, 2]
            rating = weighted_choice([1, 2, 3, 4, 5], rating_weights)
            if watch_duration < 35:
                rating = max(1, rating - 1)

            history.append(
                {
                    "watch_id": watch_id,
                    "user_id": user["user_id"],
                    "show_id": show["show_id"],
                    "watch_date": watch_time.strftime("%Y-%m-%d"),
                    "watch_duration": watch_duration,
                    "rating_given": rating,
                }
            )
            watch_id += 1

    return history


def create_denormalized_watch_file(users, shows, history):
    users_by_id = {user["user_id"]: user for user in users}
    shows_by_id = {show["show_id"]: show for show in shows}
    rows = []

    for watch in history:
        show = shows_by_id[watch["show_id"]]
        user = users_by_id[watch["user_id"]]
        rows.append(
            {
                "watch_id": watch["watch_id"],
                "user_id": watch["user_id"],
                "age": user["age"],
                "country": user["country"],
                "show_id": watch["show_id"],
                "title": show["title"],
                "genre": show["genre"],
                "release_year": show["release_year"],
                "watch_date": watch["watch_date"],
                "watch_duration": watch["watch_duration"],
                "rating_given": watch["rating_given"],
            }
        )

    write_csv(
        DATA_DIR / "netflix_watch_history.csv",
        rows,
        [
            "watch_id",
            "user_id",
            "age",
            "country",
            "show_id",
            "title",
            "genre",
            "release_year",
            "watch_date",
            "watch_duration",
            "rating_given",
        ],
    )


def main():
    random.seed(RANDOM_SEED)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    users = generate_users()
    shows = generate_shows()
    history = generate_watch_history(users, shows)

    write_csv(DATA_DIR / "users.csv", users, ["user_id", "age", "country"])
    write_csv(DATA_DIR / "shows.csv", shows, ["show_id", "title", "genre", "release_year"])
    write_csv(
        DATA_DIR / "watch_history.csv",
        history,
        ["watch_id", "user_id", "show_id", "watch_date", "watch_duration", "rating_given"],
    )
    create_denormalized_watch_file(users, shows, history)

    print(f"Generated {len(users):,} users")
    print(f"Generated {len(shows):,} shows")
    print(f"Generated {len(history):,} watch history rows")
    print(f"Saved dataset files to {DATA_DIR}")


if __name__ == "__main__":
    main()
