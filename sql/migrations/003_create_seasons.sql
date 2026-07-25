CREATE TABLE seasons (
    season_id     SERIAL PRIMARY KEY,
    season_label  VARCHAR(20) NOT NULL UNIQUE,
    start_date    DATE,
    end_date      DATE
);