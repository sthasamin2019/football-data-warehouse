OLTP Schema Design Notes — Football Data Warehouse

Date: Day 2 (Jul 22)
Source data: European football league standings, 2022–23 season (CSV, `;`-delimited)

 1. Entities

From the raw data, the following real-world entities were identified:

1. League — e.g. Premier League, La Liga, Serie A, Ligue 1, Bundesliga
2. Team — e.g. Barcelona, Napoli, Arsenal — belongs to one league
3. Season — e.g. "2022-23" — only one season present in current data, but modeled to support multiple seasons over time
4. Player — used for both top scorers and goalkeepers
5. Team Season Stats — the actual performance row (MP, W, D, L, GF, GA, xG, etc.), one per team per season snapshot
6. Team Top Scorer — link table: which player(s) scored for which team-season row, and how many goals
7. Team Goalkeeper — link table: which player(s) are goalkeeper for which team-season row

Scorer and goalkeeper are modeled as separate link tables rather than columns directly on team_season_stats, because the source data sometimes contains multiple names in one field (e.g. co-top-scorers, or two goalkeepers listed). This keeps the schema normalized and avoids losing data by picking only one name.

 2. ERD Description

leagues (1) ───< teams (many)
teams (1) ───< team_season_stats (many)
seasons (1) ───< team_season_stats (many)
team_season_stats (1) ───< team_top_scorer (many) >─── players (1)
team_season_stats (1) ───< team_goalkeeper (many) >─── players (1)


Reading the relationships:
- One league has many teams.
- One team has many season-stat rows over time (one per season/snapshot).
- One team_season_stats row can have multiple top-scorer entries and multiple goalkeeper entries.
- Each top-scorer/goalkeeper entry points to one player, and the same player could in principle appear across multiple teams/seasons over time.

 3. Table & Column Definitions

 leagues
| Column | Type | Notes |
|---|---|---|
| league_id | SERIAL PK | |
| league_name | VARCHAR | e.g. "Premier League" |
| country_code | VARCHAR(3) | e.g. "ENG" — matches CSV's Country field |

 teams
| Column | Type | Notes |
|---|---|---|
| team_id | SERIAL PK | |
| team_name | VARCHAR | e.g. "Barcelona" |
| league_id | INT FK → leagues | |

seasons
| Column | Type | Notes |
|---|---|---|
| season_id | SERIAL PK | |
| season_label | VARCHAR | e.g. "2022-23" |
| start_date | DATE | nullable for now |
| end_date | DATE | nullable for now |

players
| Column | Type | Notes |
|---|---|---|
| player_id | SERIAL PK | |
| player_name | VARCHAR | |
| role | VARCHAR | 'scorer' or 'goalkeeper' — nullable, since a player could conceptually be both |

team_season_stats
| Column | Type | Notes |
|---|---|---|
| stat_id | SERIAL PK | |
| team_id | INT FK → teams | |
| season_id | INT FK → seasons | |
| stats_date | DATE | from CSV |
| lg_rank | INT | source "Rk" column |
| mp | INT | matches played |
| w | INT | wins |
| d | INT | draws |
| l | INT | losses |
| gf | INT | goals for |
| ga | INT | goals against |
| gd | INT | goal difference |
| pts | INT | points |
| pts_per_mp | NUMERIC(4,2) | points per match |
| xg | NUMERIC(5,1) | expected goals |
| xga | NUMERIC(5,1) | expected goals against |
| xgd | NUMERIC(5,1) | expected goal difference |
| xgd_90 | NUMERIC(4,2) | expected goal diff per 90 min |
| attendance | INT | |

team_top_scorer
| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| stat_id | INT FK → team_season_stats | |
| player_id | INT FK → players | |
| goals | INT | |

team_goalkeeper
| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| stat_id | INT FK → team_season_stats | |
| player_id | INT FK → players | |



 4. Constraints & Business Rules

These will be enforced via CHECK constraints in the DDL (Day 3) and validated again as automated data quality checks (Day 6):

- w + d + l = mp — games played must reconcile with results
- gd = gf - ga — goal difference must match goals for minus goals against
- pts >= 0 — points cannot be negative
- (team_id, season_id, stats_date) must be unique in team_season_stats — no duplicate snapshots for the same team/season/date
- league_name should be restricted to the known set of 5 leagues present in this dataset (Premier League, La Liga, Serie A, Ligue 1, Bundesliga)



 5. Known Data Quality Issues (from source CSV)

Noted here so they're accounted for in extract/transform logic (Day 4–5):

- Top Team Scorer combines name + goals in one string (e.g. Robert Lewandowski - 17), and sometimes contains two co-top-scorers in a single cell (e.g. `"Ciro Immobile Mattia Zaccagni - 10)
- Goalkeeper field occasionally contains two names (e.g. Pepe Reina Gerónimo Rulli)
- Country is a proxy for league, not a direct league name — needs a lookup/mapping step
- Some player names contain non-ASCII characters that may need encoding checks (e.g. Szczęsny, Sørloth)
- stats_date values vary per row — this is a snapshot date, not the season start/end date