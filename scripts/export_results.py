import csv
import sqlite3
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
EXPORTS_DIR = ROOT_DIR / "exports"
DB_PATH = DATA_DIR / "netflix_analysis.db"


QUERIES = {
    "top_genres_per_user.csv": """
        WITH user_genre_summary AS (
            SELECT
                wh.user_id,
                s.genre,
                COUNT(*) AS sessions,
                SUM(wh.watch_duration) AS total_watch_minutes,
                AVG(wh.rating_given) AS avg_rating
            FROM watch_history AS wh
            JOIN shows AS s ON wh.show_id = s.show_id
            GROUP BY wh.user_id, s.genre
        ),
        ranked_genres AS (
            SELECT
                user_id,
                genre,
                sessions,
                total_watch_minutes,
                ROUND(avg_rating, 2) AS avg_rating,
                ROW_NUMBER() OVER (
                    PARTITION BY user_id
                    ORDER BY total_watch_minutes DESC, sessions DESC, avg_rating DESC
                ) AS genre_rank
            FROM user_genre_summary
        )
        SELECT user_id, genre_rank, genre, sessions, total_watch_minutes, avg_rating
        FROM ranked_genres
        WHERE genre_rank <= 3
        ORDER BY user_id, genre_rank;
    """,
    "binge_watching_users.csv": """
        WITH daily_user_activity AS (
            SELECT
                wh.user_id,
                wh.watch_date,
                COUNT(*) AS sessions_on_day,
                SUM(wh.watch_duration) AS watch_minutes_on_day,
                AVG(wh.rating_given) AS avg_rating_on_day
            FROM watch_history AS wh
            GROUP BY wh.user_id, wh.watch_date
        ),
        binge_days AS (
            SELECT *
            FROM daily_user_activity
            WHERE sessions_on_day >= 3
                OR watch_minutes_on_day >= 240
        )
        SELECT
            u.user_id,
            u.age,
            u.country,
            COUNT(*) AS binge_days,
            SUM(sessions_on_day) AS binge_sessions,
            SUM(watch_minutes_on_day) AS binge_watch_minutes,
            MAX(sessions_on_day) AS max_sessions_in_one_day,
            ROUND(AVG(avg_rating_on_day), 2) AS avg_binge_day_rating
        FROM binge_days AS bd
        JOIN users AS u ON bd.user_id = u.user_id
        GROUP BY u.user_id, u.age, u.country
        ORDER BY binge_days DESC, binge_watch_minutes DESC
        LIMIT 25;
    """,
    "popular_shows.csv": """
        SELECT
            s.show_id,
            s.title,
            s.genre,
            s.release_year,
            COUNT(*) AS total_sessions,
            SUM(wh.watch_duration) AS total_watch_minutes,
            ROUND(SUM(wh.watch_duration) / 60.0, 2) AS total_watch_hours,
            ROUND(AVG(wh.rating_given), 2) AS avg_rating,
            RANK() OVER (ORDER BY SUM(wh.watch_duration) DESC) AS popularity_rank
        FROM watch_history AS wh
        JOIN shows AS s ON wh.show_id = s.show_id
        GROUP BY s.show_id, s.title, s.genre, s.release_year
        ORDER BY popularity_rank
        LIMIT 25;
    """,
    "avg_duration_per_genre.csv": """
        SELECT
            s.genre,
            COUNT(*) AS total_sessions,
            SUM(wh.watch_duration) AS total_watch_minutes,
            ROUND(AVG(wh.watch_duration), 2) AS avg_watch_duration,
            ROUND(AVG(wh.rating_given), 2) AS avg_rating
        FROM watch_history AS wh
        JOIN shows AS s ON wh.show_id = s.show_id
        GROUP BY s.genre
        ORDER BY avg_watch_duration DESC;
    """,
    "monthly_engagement.csv": """
        SELECT
            strftime('%Y-%m', wh.watch_date) AS watch_month,
            SUM(wh.watch_duration) AS total_watch_minutes,
            ROUND(SUM(wh.watch_duration) / 60.0, 2) AS total_watch_hours,
            COUNT(DISTINCT wh.user_id) AS active_users,
            COUNT(*) AS sessions,
            ROUND(AVG(wh.rating_given), 2) AS avg_rating
        FROM watch_history AS wh
        GROUP BY watch_month
        ORDER BY watch_month;
    """,
    "user_retention.csv": """
        WITH active_months AS (
            SELECT DISTINCT
                user_id,
                date(strftime('%Y-%m-01', watch_date)) AS activity_month
            FROM watch_history
        ),
        user_month_lag AS (
            SELECT
                user_id,
                activity_month,
                LAG(activity_month) OVER (
                    PARTITION BY user_id
                    ORDER BY activity_month
                ) AS previous_activity_month
            FROM active_months
        ),
        monthly_retention AS (
            SELECT
                activity_month,
                COUNT(DISTINCT user_id) AS active_users,
                COUNT(DISTINCT CASE
                    WHEN previous_activity_month = date(activity_month, '-1 month')
                    THEN user_id
                END) AS retained_users
            FROM user_month_lag
            GROUP BY activity_month
        )
        SELECT
            strftime('%Y-%m', activity_month) AS activity_month,
            active_users,
            retained_users,
            ROUND(100.0 * retained_users / NULLIF(active_users, 0), 2) AS retention_rate_pct
        FROM monthly_retention
        ORDER BY activity_month;
    """,
    "recommendations.csv": """
        WITH user_genre_scores AS (
            SELECT
                wh.user_id,
                s.genre,
                SUM(wh.watch_duration) AS genre_watch_minutes,
                COUNT(*) AS genre_sessions,
                AVG(wh.rating_given) AS avg_genre_rating,
                ROW_NUMBER() OVER (
                    PARTITION BY wh.user_id
                    ORDER BY SUM(wh.watch_duration) DESC, COUNT(*) DESC, AVG(wh.rating_given) DESC
                ) AS genre_rank
            FROM watch_history AS wh
            JOIN shows AS s ON wh.show_id = s.show_id
            GROUP BY wh.user_id, s.genre
        ),
        favorite_genre AS (
            SELECT user_id, genre AS favorite_genre
            FROM user_genre_scores
            WHERE genre_rank = 1
        ),
        show_popularity AS (
            SELECT
                s.show_id,
                s.title,
                s.genre,
                s.release_year,
                COUNT(*) AS total_sessions,
                SUM(wh.watch_duration) AS total_watch_minutes,
                AVG(wh.rating_given) AS avg_rating
            FROM shows AS s
            JOIN watch_history AS wh ON s.show_id = wh.show_id
            GROUP BY s.show_id, s.title, s.genre, s.release_year
        ),
        recommendation_candidates AS (
            SELECT
                fg.user_id,
                fg.favorite_genre,
                sp.show_id,
                sp.title,
                sp.release_year,
                sp.total_sessions,
                sp.total_watch_minutes,
                ROUND(sp.avg_rating, 2) AS avg_rating,
                ROW_NUMBER() OVER (
                    PARTITION BY fg.user_id
                    ORDER BY sp.total_watch_minutes DESC, sp.avg_rating DESC
                ) AS recommendation_rank
            FROM favorite_genre AS fg
            JOIN show_popularity AS sp ON fg.favorite_genre = sp.genre
            LEFT JOIN watch_history AS watched
                ON watched.user_id = fg.user_id
                AND watched.show_id = sp.show_id
            WHERE watched.show_id IS NULL
        )
        SELECT
            user_id,
            recommendation_rank,
            favorite_genre,
            show_id,
            title,
            release_year,
            total_sessions,
            total_watch_minutes,
            avg_rating
        FROM recommendation_candidates
        WHERE recommendation_rank <= 5
        ORDER BY user_id, recommendation_rank;
    """,
}


def export_query(connection, output_name, query):
    cursor = connection.execute(query)
    rows = cursor.fetchall()
    headers = [column[0] for column in cursor.description]
    output_path = EXPORTS_DIR / output_name

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        writer.writerows(rows)

    print(f"Exported {output_name}: {len(rows):,} rows")


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError("Database not found. Run scripts/create_database.py first.")

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)

    for output_name, query in QUERIES.items():
        export_query(connection, output_name, query)

    connection.close()


if __name__ == "__main__":
    main()
