CREATE TABLE teams (
    team_id     SERIAL PRIMARY KEY,
    team_name   VARCHAR(100) NOT NULL,
    league_id   INT NOT NULL REFERENCES leagues(league_id),
    UNIQUE (team_name, league_id)
);