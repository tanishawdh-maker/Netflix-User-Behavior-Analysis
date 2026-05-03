PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS watch_history;
DROP TABLE IF EXISTS shows;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    age INTEGER,
    country TEXT
);

CREATE TABLE shows (
    show_id INTEGER PRIMARY KEY,
    title TEXT,
    genre TEXT,
    release_year INTEGER
);

CREATE TABLE watch_history (
    watch_id INTEGER PRIMARY KEY,
    user_id INTEGER,
    show_id INTEGER,
    watch_date DATE,
    watch_duration INTEGER,
    rating_given REAL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (show_id) REFERENCES shows(show_id)
);

CREATE INDEX idx_watch_history_user_id
    ON watch_history (user_id);

CREATE INDEX idx_watch_history_show_id
    ON watch_history (show_id);

CREATE INDEX idx_watch_history_watch_date
    ON watch_history (watch_date);

CREATE INDEX idx_shows_genre
    ON shows (genre);
