INSERT INTO seasons (season_label, start_date, end_date) VALUES
    ('2020-21', '2020-09-01', '2021-05-31'),
    ('2021-22', '2021-08-01', '2022-05-31'),
    ('2023-24', '2023-08-01', '2024-05-31'),
    ('2024-25', '2024-08-01', '2025-05-31')
ON CONFLICT (season_label) DO NOTHING;