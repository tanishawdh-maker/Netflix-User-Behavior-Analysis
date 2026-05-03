-- Netflix User Behavior & Recommendation Analysis
-- Dialect: SQLite

-- A. Top 3 genres per user
-- What it does: ranks every user's genres by total watch time, sessions, and average rating.
-- Business insight: identifies each user's strongest genre preferences for personalization.
WITH user_genre_summary AS (
    SELECT
        wh.user_id,
        s.genre,
        COUNT(*) AS sessions,
        SUM(wh.watch_duration) AS total_watch_minutes,
        AVG(wh.rating_given) AS avg_rating
    FROM watch_history AS wh
    JOIN shows AS s
        ON wh.show_id = s.show_id
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
SELECT
    user_id,
    genre_rank,
    genre,
    sessions,
    total_watch_minutes,
    avg_rating
FROM ranked_genres
WHERE genre_rank <= 3
ORDER BY user_id, genre_rank;


-- B. Most binge-watching users
-- What it does: finds users with multiple same-day sessions and high same-day watch duration.
-- Business insight: highlights highly engaged users who may respond well to series recommendations,
-- autoplay improvements, and retention campaigns.
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
    SELECT
        user_id,
        watch_date,
        sessions_on_day,
        watch_minutes_on_day,
        avg_rating_on_day
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
JOIN users AS u
    ON bd.user_id = u.user_id
GROUP BY u.user_id, u.age, u.country
ORDER BY binge_days DESC, binge_watch_minutes DESC
LIMIT 25;


-- C. Most popular shows by total watch time
-- What it does: ranks content by total minutes watched.
-- Business insight: shows which titles drive the most platform engagement.
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
JOIN shows AS s
    ON wh.show_id = s.show_id
GROUP BY s.show_id, s.title, s.genre, s.release_year
ORDER BY popularity_rank
LIMIT 25;


-- D. Average watch duration per genre
-- What it does: compares session length and ratings across genres.
-- Business insight: genres with longer sessions may be stronger candidates for premium placement.
SELECT
    s.genre,
    COUNT(*) AS total_sessions,
    SUM(wh.watch_duration) AS total_watch_minutes,
    ROUND(AVG(wh.watch_duration), 2) AS avg_watch_duration,
    ROUND(AVG(wh.rating_given), 2) AS avg_rating
FROM watch_history AS wh
JOIN shows AS s
    ON wh.show_id = s.show_id
GROUP BY s.genre
ORDER BY avg_watch_duration DESC;


-- E. Monthly engagement trends
-- What it does: tracks monthly watch time, active users, sessions, and rating.
-- Business insight: reveals seasonal engagement trends and months that need growth campaigns.
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


-- F. User retention across months
-- What it does: uses LAG to identify users active in consecutive months.
-- Business insight: monthly retention rate shows whether users keep returning after being active.
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


-- G. Recommendation logic
-- What it does: finds each user's top genre, then recommends popular unwatched shows from that genre.
-- Business insight: creates explainable personalized recommendations using behavior plus popularity.
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
    JOIN shows AS s
        ON wh.show_id = s.show_id
    GROUP BY wh.user_id, s.genre
),
favorite_genre AS (
    SELECT
        user_id,
        genre AS favorite_genre
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
    JOIN watch_history AS wh
        ON s.show_id = wh.show_id
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
    JOIN show_popularity AS sp
        ON fg.favorite_genre = sp.genre
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
