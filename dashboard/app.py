from pathlib import Path
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st


ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "data" / "netflix_analysis.db"


st.set_page_config(
    page_title="Netflix User Behavior & Recommendation Analysis",
    page_icon="N",
    layout="wide",
)


st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    div[data-testid="stMetric"] {
        background: #111827;
        border: 1px solid #263244;
        padding: 1rem;
        border-radius: 8px;
    }
    div[data-testid="stMetric"] label,
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #f9fafb;
    }
    h1, h2, h3 {
        letter-spacing: 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_table(query):
    with sqlite3.connect(DB_PATH) as connection:
        return pd.read_sql_query(query, connection)


def get_filtered_history(country, genre, month):
    query = """
        SELECT
            wh.watch_id,
            wh.user_id,
            u.age,
            u.country,
            wh.show_id,
            s.title,
            s.genre,
            s.release_year,
            wh.watch_date,
            strftime('%Y-%m', wh.watch_date) AS watch_month,
            wh.watch_duration,
            wh.rating_given
        FROM watch_history AS wh
        JOIN users AS u ON wh.user_id = u.user_id
        JOIN shows AS s ON wh.show_id = s.show_id
        WHERE 1 = 1
    """
    params = []

    if country != "All":
        query += " AND u.country = ?"
        params.append(country)
    if genre != "All":
        query += " AND s.genre = ?"
        params.append(genre)
    if month != "All":
        query += " AND strftime('%Y-%m', wh.watch_date) = ?"
        params.append(month)

    with sqlite3.connect(DB_PATH) as connection:
        return pd.read_sql_query(query, connection, params=params)


def metric_row(data):
    total_users = data["user_id"].nunique()
    total_shows = data["show_id"].nunique()
    total_sessions = len(data)
    total_watch_hours = data["watch_duration"].sum() / 60
    avg_rating = data["rating_given"].mean()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total users", f"{total_users:,}")
    col2.metric("Total shows", f"{total_shows:,}")
    col3.metric("Watch sessions", f"{total_sessions:,}")
    col4.metric("Watch hours", f"{total_watch_hours:,.0f}")
    col5.metric("Average rating", f"{avg_rating:.2f}")


def show_empty_state(data):
    if data.empty:
        st.warning("No records match the selected filters.")
        st.stop()


def build_recommendations(country, genre):
    query = """
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
                u.country,
                fg.favorite_genre,
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
            JOIN users AS u ON fg.user_id = u.user_id
            JOIN show_popularity AS sp ON fg.favorite_genre = sp.genre
            LEFT JOIN watch_history AS watched
                ON watched.user_id = fg.user_id
                AND watched.show_id = sp.show_id
            WHERE watched.show_id IS NULL
        )
        SELECT
            user_id,
            country,
            recommendation_rank,
            favorite_genre,
            title,
            release_year,
            total_sessions,
            total_watch_minutes,
            avg_rating
        FROM recommendation_candidates
        WHERE recommendation_rank <= 5
    """
    params = []
    if country != "All":
        query += " AND country = ?"
        params.append(country)
    if genre != "All":
        query += " AND favorite_genre = ?"
        params.append(genre)
    query += " ORDER BY user_id, recommendation_rank LIMIT 250"

    with sqlite3.connect(DB_PATH) as connection:
        return pd.read_sql_query(query, connection, params=params)


st.title("Netflix User Behavior & Recommendation Analysis")
st.caption("SQL-powered streaming analytics dashboard built with Python, SQLite, Streamlit, and Plotly.")

if not DB_PATH.exists():
    st.error("Database not found. Run `python scripts/generate_dataset.py` and `python scripts/create_database.py` first.")
    st.stop()

country_options = ["All"] + load_table("SELECT DISTINCT country FROM users ORDER BY country")["country"].tolist()
genre_options = ["All"] + load_table("SELECT DISTINCT genre FROM shows ORDER BY genre")["genre"].tolist()
month_options = ["All"] + load_table(
    "SELECT DISTINCT strftime('%Y-%m', watch_date) AS watch_month FROM watch_history ORDER BY watch_month"
)["watch_month"].tolist()

with st.sidebar:
    st.header("Filters")
    selected_country = st.selectbox("Country", country_options)
    selected_genre = st.selectbox("Genre", genre_options)
    selected_month = st.selectbox("Month", month_options)

filtered = get_filtered_history(selected_country, selected_genre, selected_month)
show_empty_state(filtered)

metric_row(filtered)

st.divider()

left, right = st.columns(2)

with left:
    popular_shows = (
        filtered.groupby(["title", "genre"], as_index=False)
        .agg(total_watch_minutes=("watch_duration", "sum"), avg_rating=("rating_given", "mean"))
        .sort_values("total_watch_minutes", ascending=False)
        .head(10)
    )
    fig = px.bar(
        popular_shows,
        x="total_watch_minutes",
        y="title",
        color="genre",
        orientation="h",
        title="Most Popular Shows by Total Watch Time",
        labels={"total_watch_minutes": "Total watch minutes", "title": "Show"},
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=430, margin=dict(l=10, r=10, t=60, b=10))
    st.plotly_chart(fig, use_container_width=True)

with right:
    genre_duration = (
        filtered.groupby("genre", as_index=False)
        .agg(avg_watch_duration=("watch_duration", "mean"), sessions=("watch_id", "count"))
        .sort_values("avg_watch_duration", ascending=False)
    )
    fig = px.bar(
        genre_duration,
        x="genre",
        y="avg_watch_duration",
        color="genre",
        title="Average Watch Duration per Genre",
        labels={"avg_watch_duration": "Average minutes", "genre": "Genre"},
    )
    fig.update_layout(showlegend=False, height=430, margin=dict(l=10, r=10, t=60, b=10))
    st.plotly_chart(fig, use_container_width=True)

left, right = st.columns(2)

with left:
    monthly = (
        filtered.groupby("watch_month", as_index=False)
        .agg(
            total_watch_minutes=("watch_duration", "sum"),
            active_users=("user_id", "nunique"),
            sessions=("watch_id", "count"),
            avg_rating=("rating_given", "mean"),
        )
        .sort_values("watch_month")
    )
    fig = px.line(
        monthly,
        x="watch_month",
        y="total_watch_minutes",
        markers=True,
        title="Monthly Engagement Trend",
        labels={"watch_month": "Month", "total_watch_minutes": "Total watch minutes"},
    )
    fig.update_traces(line_color="#e50914")
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=60, b=10))
    st.plotly_chart(fig, use_container_width=True)

with right:
    top_countries = (
        filtered.groupby("country", as_index=False)
        .agg(active_users=("user_id", "nunique"), sessions=("watch_id", "count"))
        .sort_values("active_users", ascending=False)
        .head(10)
    )
    fig = px.bar(
        top_countries,
        x="active_users",
        y="country",
        orientation="h",
        title="Top Countries by Active Users",
        labels={"active_users": "Active users", "country": "Country"},
        color="sessions",
        color_continuous_scale="Reds",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=420, margin=dict(l=10, r=10, t=60, b=10))
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Binge-Watching Users")
binge_users = (
    filtered.groupby(["user_id", "country"], as_index=False)
    .agg(
        binge_days=("watch_date", lambda dates: dates.value_counts().ge(3).sum()),
        sessions=("watch_id", "count"),
        total_watch_minutes=("watch_duration", "sum"),
        avg_rating=("rating_given", "mean"),
    )
    .query("binge_days > 0 or total_watch_minutes >= 240")
    .sort_values(["binge_days", "total_watch_minutes"], ascending=False)
    .head(25)
)
binge_users["avg_rating"] = binge_users["avg_rating"].round(2)
st.dataframe(binge_users, use_container_width=True, hide_index=True)

st.subheader("Personalized Recommendation Table")
recommendations = build_recommendations(selected_country, selected_genre)
st.dataframe(recommendations, use_container_width=True, hide_index=True)
