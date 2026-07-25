CREATE TABLE players (
    player_id     SERIAL PRIMARY KEY,
    player_name   VARCHAR(100) NOT NULL,
    role          VARCHAR(20)
);