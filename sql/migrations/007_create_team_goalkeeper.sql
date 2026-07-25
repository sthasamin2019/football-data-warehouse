CREATE TABLE team_goalkeeper (
    id          SERIAL PRIMARY KEY,
    stat_id     INT NOT NULL REFERENCES team_season_stats(stat_id),
    player_id   INT NOT NULL REFERENCES players(player_id)
);