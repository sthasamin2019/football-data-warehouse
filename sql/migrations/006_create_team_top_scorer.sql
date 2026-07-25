CREATE TABLE team_top_scorer (
    id          SERIAL PRIMARY KEY,
    stat_id     INT NOT NULL REFERENCES team_season_stats(stat_id),
    player_id   INT NOT NULL REFERENCES players(player_id),
    goals       INT NOT NULL CHECK (goals >= 0)
);