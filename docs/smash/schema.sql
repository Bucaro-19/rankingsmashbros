-- Smash GT: esquema propuesto para MySQL/MariaDB (BanaHosting, phpMyAdmin).
-- Propuesta del 6 de octubre de 2026. Ver BASE-DE-DATOS.md antes de cambiarlo.
-- Los id de players, events, sets, characters y upcoming_tournaments son los de start.gg.

CREATE TABLE players (
  id BIGINT UNSIGNED PRIMARY KEY,
  tag VARCHAR(100) NOT NULL,
  known_as VARCHAR(100) NULL,
  country_code CHAR(2) NULL,
  country_basis VARCHAR(255) NULL,
  profile_url VARCHAR(255) NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_players_tag (tag)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE events (
  id BIGINT UNSIGNED PRIMARY KEY,
  tournament_name VARCHAR(255) NOT NULL,
  event_name VARCHAR(255) NOT NULL,
  event_date DATE NOT NULL,
  country_code CHAR(2) NOT NULL,
  city VARCHAR(120) NULL,
  active_players SMALLINT UNSIGNED NULL,
  url VARCHAR(255) NULL,
  KEY idx_events_date (event_date),
  KEY idx_events_country (country_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE sets (
  id BIGINT UNSIGNED PRIMARY KEY,
  event_id BIGINT UNSIGNED NOT NULL,
  winner_id BIGINT UNSIGNED NOT NULL,
  loser_id BIGINT UNSIGNED NOT NULL,
  score VARCHAR(120) NULL,
  url VARCHAR(255) NULL,
  KEY idx_sets_event (event_id),
  KEY idx_sets_winner (winner_id),
  KEY idx_sets_loser (loser_id),
  CONSTRAINT fk_sets_event FOREIGN KEY (event_id) REFERENCES events(id),
  CONSTRAINT fk_sets_winner FOREIGN KEY (winner_id) REFERENCES players(id),
  CONSTRAINT fk_sets_loser FOREIGN KEY (loser_id) REFERENCES players(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE cuts (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  generated_at DATETIME NOT NULL,            -- UTC, igual que generatedAt del JSON
  season_year SMALLINT UNSIGNED NOT NULL,
  season_label VARCHAR(40) NOT NULL,
  method_version VARCHAR(30) NOT NULL,
  schema_version TINYINT UNSIGNED NOT NULL,
  is_final TINYINT(1) NOT NULL DEFAULT 0,    -- corte congelado de fin de temporada
  UNIQUE KEY uq_cuts_generated (generated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE rankings (
  cut_id INT UNSIGNED NOT NULL,
  scope ENUM('combined','guatemala') NOT NULL,
  player_id BIGINT UNSIGNED NOT NULL,
  rank_position SMALLINT UNSIGNED NOT NULL,
  previous_rank SMALLINT UNSIGNED NULL,
  rating SMALLINT NOT NULL,
  wins SMALLINT UNSIGNED NOT NULL,
  losses SMALLINT UNSIGNED NOT NULL,
  events_count SMALLINT UNSIGNED NOT NULL,
  PRIMARY KEY (cut_id, scope, player_id),
  UNIQUE KEY uq_rankings_position (cut_id, scope, rank_position),
  KEY idx_rankings_player (player_id),
  CONSTRAINT fk_rankings_cut FOREIGN KEY (cut_id) REFERENCES cuts(id) ON DELETE CASCADE,
  CONSTRAINT fk_rankings_player FOREIGN KEY (player_id) REFERENCES players(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE characters (
  id INT UNSIGNED PRIMARY KEY,
  name VARCHAR(60) NOT NULL,
  slug VARCHAR(60) NOT NULL,
  UNIQUE KEY uq_characters_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE player_characters (
  cut_id INT UNSIGNED NOT NULL,
  scope ENUM('combined','guatemala') NOT NULL,
  player_id BIGINT UNSIGNED NOT NULL,
  character_id INT UNSIGNED NOT NULL,
  games SMALLINT UNSIGNED NOT NULL,
  PRIMARY KEY (cut_id, scope, player_id, character_id),
  KEY idx_pc_character (character_id),
  CONSTRAINT fk_pc_cut FOREIGN KEY (cut_id) REFERENCES cuts(id) ON DELETE CASCADE,
  CONSTRAINT fk_pc_player FOREIGN KEY (player_id) REFERENCES players(id),
  CONSTRAINT fk_pc_character FOREIGN KEY (character_id) REFERENCES characters(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE users (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  startgg_user_id BIGINT UNSIGNED NOT NULL,  -- identidad que devuelve el login de start.gg
  player_id BIGINT UNSIGNED NULL,            -- jugador del ranking al que corresponde
  display_name VARCHAR(100) NULL,
  chosen_main_id INT UNSIGNED NULL,          -- main elegido por la persona
  role ENUM('player','organizer','admin') NOT NULL DEFAULT 'player',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login_at DATETIME NULL,
  UNIQUE KEY uq_users_startgg (startgg_user_id),
  UNIQUE KEY uq_users_player (player_id),
  CONSTRAINT fk_users_player FOREIGN KEY (player_id) REFERENCES players(id),
  CONSTRAINT fk_users_main FOREIGN KEY (chosen_main_id) REFERENCES characters(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE upcoming_tournaments (
  id BIGINT UNSIGNED PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  starts_at DATETIME NOT NULL,
  city VARCHAR(120) NULL,
  venue VARCHAR(255) NULL,
  country_code CHAR(2) NOT NULL DEFAULT 'GT',
  url VARCHAR(255) NOT NULL,
  organizer_user_id INT UNSIGNED NULL,
  fetched_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_upcoming_starts (starts_at),
  CONSTRAINT fk_upcoming_organizer FOREIGN KEY (organizer_user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
