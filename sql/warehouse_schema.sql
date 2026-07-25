
CREATE TABLE dim_team (
    team_key      SERIAL PRIMARY KEY,
    team_name     VARCHAR(100) NOT NULL,
    league_name   VARCHAR(50) NOT NULL,
    country_code  VARCHAR(3),
    UNIQUE (team_name, league_name)
);

CREATE TABLE dim_season (
    season_key    SERIAL PRIMARY KEY,
    season_label  VARCHAR(20) NOT NULL UNIQUE,
    start_date    DATE,
    end_date      DATE
);

CREATE TABLE dim_player (
    player_key    SERIAL PRIMARY KEY,
    player_name   VARCHAR(100) NOT NULL,
    role          VARCHAR(20),
    UNIQUE (player_name, role)
);

CREATE TABLE dim_date (
    date_key      INT PRIMARY KEY,
    full_date     DATE NOT NULL UNIQUE,
    year          INT NOT NULL,
    month         INT NOT NULL,
    month_name    VARCHAR(20) NOT NULL,
    quarter       INT NOT NULL,
    day_of_week   VARCHAR(20) NOT NULL
);

CREATE TABLE fact_team_season_performance (
    fact_id         SERIAL PRIMARY KEY,
    team_key        INT NOT NULL REFERENCES dim_team(team_key),
    season_key      INT NOT NULL REFERENCES dim_season(season_key),
    date_key        INT NOT NULL REFERENCES dim_date(date_key),
    top_scorer_key  INT REFERENCES dim_player(player_key),
    goalkeeper_key  INT REFERENCES dim_player(player_key),
    mp INT, w INT, d INT, l INT,
    gf INT, ga INT, gd INT,
    pts INT,
    pts_per_mp NUMERIC(4,2),
    xg NUMERIC(5,1), xga NUMERIC(5,1), xgd NUMERIC(5,1), xgd_90 NUMERIC(4,2),
    attendance INT,
    source VARCHAR(20),
    UNIQUE (team_key, season_key, date_key)
);
