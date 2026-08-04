
ALTER TABLE team_season_stats ADD COLUMN IF NOT EXISTS source VARCHAR(20);


UPDATE team_season_stats tss
SET source = CASE WHEN t.team_name ~ '\d+$' THEN 'synthetic' ELSE 'real' END
FROM teams t
WHERE tss.team_id = t.team_id;
