-- Analysis-only public history. NOT cut membership or national eligibility.
-- Owner must explicitly approve applying this migration in production.
SET NAMES utf8mb4;
SET time_zone = '+00:00';
CREATE TABLE IF NOT EXISTS analysis_context_batches (
 source_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 source_event_id BIGINT UNSIGNED NOT NULL,
 season_year SMALLINT UNSIGNED NOT NULL,
 captured_at DATETIME(6) NOT NULL,
 imported_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS analysis_context_players (
 player_id BIGINT UNSIGNED NOT NULL,
 season_year SMALLINT UNSIGNED NOT NULL,
 source_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 PRIMARY KEY (season_year,player_id),
 CONSTRAINT fk_analysis_player FOREIGN KEY (player_id) REFERENCES players(id),
 CONSTRAINT fk_analysis_batch FOREIGN KEY (source_hash) REFERENCES analysis_context_batches(source_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS analysis_game_scores (
 game_id BIGINT UNSIGNED PRIMARY KEY,
 entrant1_score INT NULL,
 entrant2_score INT NULL,
 CONSTRAINT fk_analysis_game FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT IGNORE INTO schema_migrations (version) VALUES ('007_analysis_context');
