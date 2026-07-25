CREATE TABLE leagues (
    league_id     SERIAL PRIMARY KEY,
    league_name   VARCHAR(50) NOT NULL,
    country_code  VARCHAR(3) NOT NULL UNIQUE
);