-- Smash GT v1: instalar en una BASE VACIA seleccionada en phpMyAdmin.
-- MySQL 8.0.16+ / MariaDB 10.6+. UTC. No crea usuarios ni borra datos.
-- IDs externos=start.gg; internos=AUTO_INCREMENT. IF NOT EXISTS no migra tablas antiguas.
SET NAMES utf8mb4;
SET time_zone = '+00:00';

CREATE TABLE IF NOT EXISTS schema_migrations (
 version VARCHAR(80) PRIMARY KEY,
 installed_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS players (
 id BIGINT UNSIGNED PRIMARY KEY, tag VARCHAR(100) NOT NULL, known_as VARCHAR(100) NULL,
 country_code CHAR(2) NULL, country_basis VARCHAR(255) NULL, profile_url VARCHAR(512) NULL,
 synced_at DATETIME(6) NULL,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 KEY idx_players_tag (tag)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS characters (
 id INT UNSIGNED PRIMARY KEY, name VARCHAR(80) NOT NULL, slug VARCHAR(80) NOT NULL,
 icon_url VARCHAR(512) NULL, portrait_url VARCHAR(512) NULL,
 UNIQUE KEY uq_characters_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS users (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, startgg_user_id BIGINT UNSIGNED NOT NULL,
 player_id BIGINT UNSIGNED NULL, display_name VARCHAR(100) NULL,
 status ENUM('active','disabled') NOT NULL DEFAULT 'active',
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), last_login_at DATETIME(6) NULL,
 UNIQUE KEY uq_users_startgg (startgg_user_id), UNIQUE KEY uq_users_player (player_id),
 CONSTRAINT fk_users_player FOREIGN KEY (player_id) REFERENCES players(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Roles de producto; NO conceden permisos de escritura en start.gg.
CREATE TABLE IF NOT EXISTS user_roles (
 user_id BIGINT UNSIGNED NOT NULL, role ENUM('player','organizer','admin') NOT NULL,
 granted_by BIGINT UNSIGNED NULL, granted_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 PRIMARY KEY (user_id, role),
 CONSTRAINT fk_roles_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
 CONSTRAINT fk_roles_granter FOREIGN KEY (granted_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Main y hasta dos secundarios elegidos; no modifica el uso automatico.
CREATE TABLE IF NOT EXISTS user_characters (
 user_id BIGINT UNSIGNED NOT NULL, position TINYINT UNSIGNED NOT NULL,
 character_id INT UNSIGNED NOT NULL, updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 PRIMARY KEY (user_id, position), UNIQUE KEY uq_user_character (user_id, character_id),
 CONSTRAINT ck_user_character_position CHECK (position BETWEEN 1 AND 3),
 CONSTRAINT fk_uc_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
 CONSTRAINT fk_uc_character FOREIGN KEY (character_id) REFERENCES characters(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Cifrado autenticado en PHP; llave y client_secret fuera de la base y de Git.
-- No guardar tokens en claro ni en payloads/logs de otras tablas.
CREATE TABLE IF NOT EXISTS oauth_connections (
 user_id BIGINT UNSIGNED PRIMARY KEY, scopes TEXT NOT NULL,
 access_token_encrypted MEDIUMBLOB NULL, refresh_token_encrypted MEDIUMBLOB NULL,
 encryption_key_id VARCHAR(80) NULL, expires_at DATETIME(6) NULL, revoked_at DATETIME(6) NULL,
 updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 CONSTRAINT fk_oauth_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
 CONSTRAINT ck_oauth_key CHECK ((access_token_encrypted IS NULL AND refresh_token_encrypted IS NULL) OR encryption_key_id IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Una sola entidad para agenda, torneos en curso e historial.
CREATE TABLE IF NOT EXISTS tournaments (
 id BIGINT UNSIGNED PRIMARY KEY, name VARCHAR(255) NOT NULL, slug VARCHAR(255) NULL,
 starts_at DATETIME(6) NULL, ends_at DATETIME(6) NULL, timezone_name VARCHAR(80) NULL,
 city VARCHAR(120) NULL, venue VARCHAR(255) NULL, country_code CHAR(2) NULL,
 url VARCHAR(512) NULL, is_online TINYINT(1) NULL, source_state INT NULL,
 source_updated_at DATETIME(6) NULL, synced_at DATETIME(6) NULL,
 KEY idx_tournaments_upcoming (starts_at, country_code),
 CONSTRAINT ck_tournament_dates CHECK (ends_at IS NULL OR starts_at IS NULL OR ends_at >= starts_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS events (
 id BIGINT UNSIGNED PRIMARY KEY, tournament_id BIGINT UNSIGNED NOT NULL,
 name VARCHAR(255) NOT NULL, videogame_id BIGINT UNSIGNED NULL, entrant_size SMALLINT UNSIGNED NULL,
 starts_at DATETIME(6) NULL, source_state INT NULL, registered_entrants INT UNSIGNED NULL,
 active_players INT UNSIGNED NULL, url VARCHAR(512) NULL,
 source_updated_at DATETIME(6) NULL, synced_at DATETIME(6) NULL,
 KEY idx_events_game_date (videogame_id, starts_at),
 CONSTRAINT fk_events_tournament FOREIGN KEY (tournament_id) REFERENCES tournaments(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Atribucion de eventos y permiso por torneo, pendiente hasta verificar su fuente.
-- Antes de una mutacion, verificar otra vez acceso real; no confiar solo en esta cache.
CREATE TABLE IF NOT EXISTS tournament_staff (
 tournament_id BIGINT UNSIGNED NOT NULL, user_id BIGINT UNSIGNED NOT NULL,
 role ENUM('organizer','reporter','manager') NOT NULL,
 verification_status ENUM('pending','verified','revoked') NOT NULL DEFAULT 'pending',
 verification_source VARCHAR(80) NULL, verified_by BIGINT UNSIGNED NULL, verified_at DATETIME(6) NULL,
 PRIMARY KEY (tournament_id, user_id, role), KEY idx_staff_user (user_id, verification_status),
 CONSTRAINT fk_staff_tournament FOREIGN KEY (tournament_id) REFERENCES tournaments(id),
 CONSTRAINT fk_staff_user FOREIGN KEY (user_id) REFERENCES users(id),
 CONSTRAINT fk_staff_verifier FOREIGN KEY (verified_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS entrants (
 id BIGINT UNSIGNED PRIMARY KEY, event_id BIGINT UNSIGNED NOT NULL, name VARCHAR(255) NOT NULL,
 registration_status ENUM('registered','withdrawn','unknown') NOT NULL DEFAULT 'unknown',
 checked_in_at DATETIME(6) NULL, competitive_sets INT UNSIGNED NULL,
 final_placement INT UNSIGNED NULL, synced_at DATETIME(6) NULL,
 UNIQUE KEY uq_entrant_event (id, event_id), KEY idx_entrants_event_placement (event_id, final_placement),
 CONSTRAINT fk_entrants_event FOREIGN KEY (event_id) REFERENCES events(id),
 CONSTRAINT ck_entrant_placement CHECK (final_placement IS NULL OR final_placement > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS entrant_players (
 entrant_id BIGINT UNSIGNED NOT NULL, player_id BIGINT UNSIGNED NOT NULL,
 participant_id BIGINT UNSIGNED NULL, registered_tag VARCHAR(100) NULL,
 PRIMARY KEY (entrant_id, player_id), KEY idx_ep_player (player_id),
 CONSTRAINT fk_ep_entrant FOREIGN KEY (entrant_id) REFERENCES entrants(id),
 CONSTRAINT fk_ep_player FOREIGN KEY (player_id) REFERENCES players(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Puede existir sin rival conocido y sin ganador. Estar aqui no concede puntos.
CREATE TABLE IF NOT EXISTS sets (
 id BIGINT UNSIGNED PRIMARY KEY, event_id BIGINT UNSIGNED NOT NULL, source_state INT NULL,
 status ENUM('unknown','pending','ready','in_progress','completed','cancelled') NOT NULL DEFAULT 'unknown',
 outcome_type ENUM('unknown','competitive','dq','bye','walkover') NOT NULL DEFAULT 'unknown',
 winner_entrant_id BIGINT UNSIGNED NULL, display_score VARCHAR(255) NULL,
 round_number INT NULL, round_label VARCHAR(120) NULL,
 bracket_side ENUM('unknown','winners','losers','other') NOT NULL DEFAULT 'unknown',
 phase_id BIGINT UNSIGNED NULL, phase_group_id BIGINT UNSIGNED NULL, station_label VARCHAR(120) NULL,
 best_of SMALLINT UNSIGNED NULL, scheduled_at DATETIME(6) NULL, called_at DATETIME(6) NULL,
 started_at DATETIME(6) NULL, completed_at DATETIME(6) NULL, url VARCHAR(512) NULL,
 source_updated_at DATETIME(6) NULL, synced_at DATETIME(6) NULL,
 source_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
 UNIQUE KEY uq_set_event (id, event_id), KEY idx_sets_event_status (event_id, status),
 CONSTRAINT fk_sets_event FOREIGN KEY (event_id) REFERENCES events(id),
 CONSTRAINT fk_sets_winner FOREIGN KEY (winner_entrant_id, event_id) REFERENCES entrants(id, event_id),
 CONSTRAINT ck_set_pending_winner CHECK (status = 'completed' OR winner_entrant_id IS NULL),
 CONSTRAINT ck_set_best_of CHECK (best_of IS NULL OR best_of > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS set_slots (
 set_id BIGINT UNSIGNED NOT NULL, slot_index TINYINT UNSIGNED NOT NULL,
 event_id BIGINT UNSIGNED NOT NULL, entrant_id BIGINT UNSIGNED NULL,
 score SMALLINT UNSIGNED NULL, is_dq TINYINT(1) NOT NULL DEFAULT 0,
 PRIMARY KEY (set_id, slot_index), UNIQUE KEY uq_set_entrant (set_id, entrant_id),
 KEY idx_slots_entrant (entrant_id, set_id),
 CONSTRAINT ck_slot_index CHECK (slot_index IN (0, 1)),
 CONSTRAINT fk_slots_set FOREIGN KEY (set_id, event_id) REFERENCES sets(id, event_id),
 CONSTRAINT fk_slots_entrant FOREIGN KEY (entrant_id, event_id) REFERENCES entrants(id, event_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS games (
 id BIGINT UNSIGNED PRIMARY KEY, set_id BIGINT UNSIGNED NOT NULL,
 game_number SMALLINT UNSIGNED NOT NULL, winner_entrant_id BIGINT UNSIGNED NULL,
 stage_id BIGINT UNSIGNED NULL, synced_at DATETIME(6) NULL,
 UNIQUE KEY uq_game_number (set_id, game_number), UNIQUE KEY uq_game_set (id, set_id),
 CONSTRAINT fk_games_set FOREIGN KEY (set_id) REFERENCES sets(id),
 CONSTRAINT fk_games_winner FOREIGN KEY (set_id, winner_entrant_id) REFERENCES set_slots(set_id, entrant_id),
 CONSTRAINT ck_game_number CHECK (game_number > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Conservar multiples picks permite auditar selecciones ambiguas; no inventar un main.
CREATE TABLE IF NOT EXISTS game_selections (
 game_id BIGINT UNSIGNED NOT NULL, set_id BIGINT UNSIGNED NOT NULL,
 entrant_id BIGINT UNSIGNED NOT NULL, character_id INT UNSIGNED NOT NULL,
 PRIMARY KEY (game_id, entrant_id, character_id),
 CONSTRAINT fk_gs_game FOREIGN KEY (game_id, set_id) REFERENCES games(id, set_id),
 CONSTRAINT fk_gs_entrant FOREIGN KEY (set_id, entrant_id) REFERENCES set_slots(set_id, entrant_id),
 CONSTRAINT fk_gs_character FOREIGN KEY (character_id) REFERENCES characters(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Importacion transaccional, una vez por identidad/hash. No editar cortes publicados.
CREATE TABLE IF NOT EXISTS cuts (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, generated_at DATETIME(6) NOT NULL,
 season_year SMALLINT UNSIGNED NOT NULL, season_label VARCHAR(80) NOT NULL,
 method_version VARCHAR(80) NOT NULL, schema_version SMALLINT UNSIGNED NOT NULL,
 character_captured_at DATETIME(6) NULL, public_snapshot LONGTEXT NOT NULL,
 source_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 status ENUM('importing','published','failed') NOT NULL DEFAULT 'importing',
 is_final TINYINT(1) NOT NULL DEFAULT 0, imported_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 UNIQUE KEY uq_cut_identity (generated_at, season_year, method_version), UNIQUE KEY uq_cut_hash (source_hash),
 KEY idx_cuts_season_status (season_year, status),
 CONSTRAINT ck_cut_snapshot CHECK (JSON_VALID(public_snapshot))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Copias de metadatos y resultados: una correccion del torneo no reescribe el pasado.
CREATE TABLE IF NOT EXISTS cut_events (
 cut_id BIGINT UNSIGNED NOT NULL, scope ENUM('combined','guatemala') NOT NULL,
 event_id BIGINT UNSIGNED NOT NULL, tournament_name VARCHAR(255) NOT NULL,
 event_name VARCHAR(255) NOT NULL, event_date DATE NOT NULL, country_code CHAR(2) NULL,
 active_players INT UNSIGNED NULL, eligibility_reason VARCHAR(255) NULL,
 weight DECIMAL(12,6) NULL, url VARCHAR(512) NULL,
 PRIMARY KEY (cut_id, scope, event_id),
 CONSTRAINT fk_ce_cut FOREIGN KEY (cut_id) REFERENCES cuts(id),
 CONSTRAINT fk_ce_event FOREIGN KEY (event_id) REFERENCES events(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cut_set_results (
 cut_id BIGINT UNSIGNED NOT NULL, scope ENUM('combined','guatemala') NOT NULL,
 set_id BIGINT UNSIGNED NOT NULL, event_id BIGINT UNSIGNED NOT NULL,
 winner_id BIGINT UNSIGNED NOT NULL, loser_id BIGINT UNSIGNED NOT NULL,
 winner_tag VARCHAR(100) NOT NULL, loser_tag VARCHAR(100) NOT NULL,
 winner_score SMALLINT UNSIGNED NULL, loser_score SMALLINT UNSIGNED NULL, display_score VARCHAR(255) NULL,
 source_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
 PRIMARY KEY (cut_id, scope, set_id),
 KEY idx_csr_winner (winner_id, cut_id, scope), KEY idx_csr_loser (loser_id, cut_id, scope),
 CONSTRAINT fk_csr_event FOREIGN KEY (cut_id, scope, event_id) REFERENCES cut_events(cut_id, scope, event_id),
 CONSTRAINT fk_csr_set FOREIGN KEY (set_id, event_id) REFERENCES sets(id, event_id),
 CONSTRAINT fk_csr_winner FOREIGN KEY (winner_id) REFERENCES players(id),
 CONSTRAINT fk_csr_loser FOREIGN KEY (loser_id) REFERENCES players(id),
 CONSTRAINT ck_csr_distinct CHECK (winner_id <> loser_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS rankings (
 cut_id BIGINT UNSIGNED NOT NULL, scope ENUM('combined','guatemala') NOT NULL,
 player_id BIGINT UNSIGNED NOT NULL, player_tag VARCHAR(100) NOT NULL,
 rank_position INT UNSIGNED NOT NULL, previous_rank INT UNSIGNED NULL, previous_cut_id BIGINT UNSIGNED NULL, previous_cut_at DATETIME(6) NULL,
 rating INT NOT NULL, wins INT UNSIGNED NOT NULL, losses INT UNSIGNED NOT NULL, events_count INT UNSIGNED NOT NULL,
 sets_queried INT UNSIGNED NOT NULL DEFAULT 0, sets_with_selections INT UNSIGNED NOT NULL DEFAULT 0,
 games_with_selections INT UNSIGNED NOT NULL DEFAULT 0, ambiguous_games INT UNSIGNED NOT NULL DEFAULT 0,
 PRIMARY KEY (cut_id, scope, player_id), UNIQUE KEY uq_ranking_position (cut_id, scope, rank_position),
 KEY idx_rankings_player (player_id, scope, cut_id),
 CONSTRAINT fk_rank_cut FOREIGN KEY (cut_id) REFERENCES cuts(id),
 CONSTRAINT fk_rank_player FOREIGN KEY (player_id) REFERENCES players(id),
 CONSTRAINT fk_rank_previous FOREIGN KEY (previous_cut_id, scope, player_id) REFERENCES rankings(cut_id, scope, player_id),
 CONSTRAINT ck_rank_position CHECK (rank_position > 0 AND (previous_rank IS NULL OR previous_rank > 0)),
 CONSTRAINT ck_rank_previous CHECK ((previous_rank IS NULL AND previous_cut_at IS NULL AND previous_cut_id IS NULL) OR (previous_rank IS NOT NULL AND previous_cut_at IS NOT NULL AND (previous_cut_id IS NULL OR previous_cut_id <> cut_id))),
 CONSTRAINT ck_rank_coverage CHECK (sets_with_selections <= sets_queried)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS player_characters (
 cut_id BIGINT UNSIGNED NOT NULL, scope ENUM('combined','guatemala') NOT NULL,
 player_id BIGINT UNSIGNED NOT NULL, character_id INT UNSIGNED NOT NULL, games INT UNSIGNED NOT NULL,
 PRIMARY KEY (cut_id, scope, player_id, character_id), KEY idx_pc_character (character_id),
 CONSTRAINT fk_pc_rank FOREIGN KEY (cut_id, scope, player_id) REFERENCES rankings(cut_id, scope, player_id),
 CONSTRAINT fk_pc_character FOREIGN KEY (character_id) REFERENCES characters(id),
 CONSTRAINT ck_pc_games CHECK (games > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Versiones conservadas: coincidencia no equivale a publicacion en start.gg.
CREATE TABLE IF NOT EXISTS result_submissions (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, set_id BIGINT UNSIGNED NOT NULL,
 user_id BIGINT UNSIGNED NOT NULL, revision INT UNSIGNED NOT NULL, winner_entrant_id BIGINT UNSIGNED NOT NULL,
 score_slot0 SMALLINT UNSIGNED NOT NULL, score_slot1 SMALLINT UNSIGNED NOT NULL,
 based_on_source_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 status ENUM('pending','matched','disputed','superseded','approved','rejected','stale') NOT NULL DEFAULT 'pending',
 submitted_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 UNIQUE KEY uq_submission_revision (set_id, user_id, revision), UNIQUE KEY uq_submission_set (id, set_id),
 KEY idx_submissions_pending (set_id, status),
 CONSTRAINT fk_submission_set FOREIGN KEY (set_id) REFERENCES sets(id),
 CONSTRAINT fk_submission_user FOREIGN KEY (user_id) REFERENCES users(id),
 CONSTRAINT fk_submission_winner FOREIGN KEY (set_id, winner_entrant_id) REFERENCES set_slots(set_id, entrant_id),
 CONSTRAINT ck_submission_revision CHECK (revision > 0), CONSTRAINT ck_submission_score CHECK (score_slot0 <> score_slot1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS result_reviews (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, submission_id BIGINT UNSIGNED NOT NULL,
 reviewer_id BIGINT UNSIGNED NOT NULL, decision ENUM('approved','rejected','stale') NOT NULL,
 source_hash_checked CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 note VARCHAR(1000) NULL, reviewed_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 UNIQUE KEY uq_review_submission (submission_id),
 CONSTRAINT fk_review_submission FOREIGN KEY (submission_id) REFERENCES result_submissions(id),
 CONSTRAINT fk_review_user FOREIGN KEY (reviewer_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Un intento logico unico; un timeout requiere reconciliar antes de reintentar.
CREATE TABLE IF NOT EXISTS result_publish_attempts (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, set_id BIGINT UNSIGNED NOT NULL,
 submission_id BIGINT UNSIGNED NOT NULL, reporter_id BIGINT UNSIGNED NOT NULL,
 idempotency_key CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 status ENUM('queued','sending','succeeded','conflict','unknown','failed') NOT NULL DEFAULT 'queued',
 source_hash_checked CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 response_summary TEXT NULL, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), finished_at DATETIME(6) NULL,
 UNIQUE KEY uq_publish_key (idempotency_key), UNIQUE KEY uq_publish_submission (submission_id),
 KEY idx_publish_set (set_id, status),
 CONSTRAINT fk_publish_submission FOREIGN KEY (submission_id, set_id) REFERENCES result_submissions(id, set_id),
 CONSTRAINT fk_publish_reporter FOREIGN KEY (reporter_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audit_log (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, actor_user_id BIGINT UNSIGNED NULL,
 action VARCHAR(80) NOT NULL, entity_type VARCHAR(80) NOT NULL, entity_id VARCHAR(80) NOT NULL,
 details TEXT NULL, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 KEY idx_audit_entity (entity_type, entity_id, created_at),
 CONSTRAINT fk_audit_actor FOREIGN KEY (actor_user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS notification_preferences (
 user_id BIGINT UNSIGNED PRIMARY KEY, match_ready TINYINT(1) NOT NULL DEFAULT 0,
 result_review TINYINT(1) NOT NULL DEFAULT 0, weekly_rank TINYINT(1) NOT NULL DEFAULT 0,
 updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 CONSTRAINT fk_np_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Endpoints privados de entrega, eliminar al revocar acceso.
CREATE TABLE IF NOT EXISTS push_subscriptions (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, user_id BIGINT UNSIGNED NOT NULL, endpoint TEXT NOT NULL,
 endpoint_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 p256dh VARCHAR(255) NOT NULL, auth_secret VARCHAR(255) NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), revoked_at DATETIME(6) NULL,
 UNIQUE KEY uq_push_endpoint (endpoint_hash), UNIQUE KEY uq_push_user (id, user_id),
 CONSTRAINT fk_push_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS notifications (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, user_id BIGINT UNSIGNED NOT NULL, type VARCHAR(80) NOT NULL,
 set_id BIGINT UNSIGNED NULL, cut_id BIGINT UNSIGNED NULL,
 deduplication_key CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 title VARCHAR(200) NOT NULL, body VARCHAR(1000) NOT NULL, target_path VARCHAR(512) NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), read_at DATETIME(6) NULL, expires_at DATETIME(6) NULL,
 UNIQUE KEY uq_notification_dedup (user_id, deduplication_key), UNIQUE KEY uq_notification_user (id, user_id),
 KEY idx_notifications_inbox (user_id, read_at, created_at),
 CONSTRAINT fk_notification_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
 CONSTRAINT fk_notification_set FOREIGN KEY (set_id) REFERENCES sets(id),
 CONSTRAINT fk_notification_cut FOREIGN KEY (cut_id) REFERENCES cuts(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS notification_deliveries (
 notification_id BIGINT UNSIGNED NOT NULL, subscription_id BIGINT UNSIGNED NOT NULL, user_id BIGINT UNSIGNED NOT NULL,
 status ENUM('queued','sending','delivered','failed','expired') NOT NULL DEFAULT 'queued',
 attempts INT UNSIGNED NOT NULL DEFAULT 0, last_attempt_at DATETIME(6) NULL, error_code VARCHAR(80) NULL,
 PRIMARY KEY (notification_id, subscription_id), KEY idx_delivery_queue (status, last_attempt_at),
 CONSTRAINT fk_delivery_notice FOREIGN KEY (notification_id, user_id) REFERENCES notifications(id, user_id) ON DELETE CASCADE,
 CONSTRAINT fk_delivery_push FOREIGN KEY (subscription_id, user_id) REFERENCES push_subscriptions(id, user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sync_jobs (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 kind ENUM('ranking_import','tournament_live','player_history','survey_import') NOT NULL,
 deduplication_key CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 tournament_id BIGINT UNSIGNED NULL, requesting_user_id BIGINT UNSIGNED NULL,
 status ENUM('queued','running','succeeded','failed') NOT NULL DEFAULT 'queued', requests_count INT UNSIGNED NOT NULL DEFAULT 0,
 started_at DATETIME(6) NULL, finished_at DATETIME(6) NULL, next_attempt_at DATETIME(6) NULL, error_code VARCHAR(80) NULL,
 UNIQUE KEY uq_sync_dedup (deduplication_key), KEY idx_sync_queue (status, next_attempt_at),
 CONSTRAINT fk_sync_tournament FOREIGN KEY (tournament_id) REFERENCES tournaments(id),
 CONSTRAINT fk_sync_user FOREIGN KEY (requesting_user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Encuesta anonima: sin nombre, correo, IP ni relacion a users.
CREATE TABLE IF NOT EXISTS survey_responses (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, submitted_at DATETIME(6) NOT NULL,
 season_year SMALLINT UNSIGNED NOT NULL, role VARCHAR(30) NOT NULL, eligibility VARCHAR(40) NOT NULL,
 minimum_activity VARCHAR(40) NOT NULL, international VARCHAR(40) NOT NULL,
 clarity TINYINT UNSIGNED NOT NULL, confidence TINYINT UNSIGNED NOT NULL, source_url VARCHAR(512) NULL,
 comment TEXT NULL, is_test TINYINT(1) NOT NULL DEFAULT 0,
 import_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
 UNIQUE KEY uq_survey_import (import_hash), KEY idx_survey_season (season_year, submitted_at),
 CONSTRAINT ck_survey_scores CHECK (clarity BETWEEN 1 AND 5 AND confidence BETWEEN 1 AND 5),
 CONSTRAINT ck_survey_comment CHECK (comment IS NULL OR CHAR_LENGTH(comment) <= 2000)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO schema_migrations (version) VALUES ('001_accounts_competition');

-- Generated by scripts/database/build_character_seed.cjs. Run AFTER schema.sql.
-- Repeatable: refreshes catalog labels/assets, never deletes player selections.
SET NAMES utf8mb4;
INSERT INTO characters (id, name, slug, icon_url, portrait_url) VALUES
(1302, 'Mario', 'mario', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/mario.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/mario.png'),
(1280, 'Donkey Kong', 'donkey_kong', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/donkey_kong.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/donkey_kong.png'),
(1296, 'Link', 'link', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/link.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/link.png'),
(1328, 'Samus', 'samus', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/samus.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/samus.png'),
(1338, 'Yoshi', 'yoshi', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/yoshi.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/yoshi.png'),
(1295, 'Kirby', 'kirby', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/kirby.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/kirby.png'),
(1286, 'Fox', 'fox', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/fox.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/fox.png'),
(1319, 'Pikachu', 'pikachu', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/pikachu.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/pikachu.png'),
(1301, 'Luigi', 'luigi', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/luigi.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/luigi.png'),
(1313, 'Ness', 'ness', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/ness.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/ness.png'),
(1274, 'Captain Falcon', 'captain_falcon', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/captain_falcon.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/captain_falcon.png'),
(1293, 'Jigglypuff', 'jigglypuff', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/jigglypuff.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/jigglypuff.png'),
(1317, 'Peach', 'peach', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/peach.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/peach.png'),
(1273, 'Bowser', 'bowser', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/bowser.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/bowser.png'),
(1290, 'Ice Climbers', 'ice_climbers', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/ice_climbers.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/ice_climbers.png'),
(1329, 'Sheik', 'sheik', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/sheik.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/sheik.png'),
(1340, 'Zelda', 'zelda', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/zelda.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/zelda.png'),
(1282, 'Dr. Mario', 'dr_mario', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/dr_mario.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/dr_mario.png'),
(1318, 'Pichu', 'pichu', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/pichu.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/pichu.png'),
(1285, 'Falco', 'falco', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/falco.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/falco.png'),
(1304, 'Marth', 'marth', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/marth.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/marth.png'),
(1339, 'Young Link', 'young_link', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/young_link.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/young_link.png'),
(1287, 'Ganondorf', 'ganondorf', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/ganondorf.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/ganondorf.png'),
(1310, 'Mewtwo', 'mewtwo', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/mewtwo.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/mewtwo.png'),
(1326, 'Roy', 'roy', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/roy.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/roy.png'),
(1405, 'Mr. Game & Watch', 'mr_game_and_watch', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/mr_game_and_watch.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/mr_game_and_watch.png'),
(1307, 'Meta Knight', 'meta_knight', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/meta_knight.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/meta_knight.png'),
(1320, 'Pit', 'pit', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/pit.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/pit.png'),
(1341, 'Zero Suit Samus', 'zero_suit_samus', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/zero_suit_samus.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/zero_suit_samus.png'),
(1335, 'Wario', 'wario', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/wario.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/wario.png'),
(1331, 'Snake', 'snake', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/snake.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/snake.png'),
(1291, 'Ike', 'ike', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/ike.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/ike.png'),
(1321, 'Pokémon Trainer', 'pokemon_trainer', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/pokemon_trainer.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/pokemon_trainer.png'),
(1279, 'Diddy Kong', 'diddy_kong', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/diddy_kong.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/diddy_kong.png'),
(1299, 'Lucas', 'lucas', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/lucas.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/lucas.png'),
(1332, 'Sonic', 'sonic', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/sonic.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/sonic.png'),
(1294, 'King Dedede', 'king_dedede', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/king_dedede.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/king_dedede.png'),
(1314, 'Olimar', 'olimar', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/olimar.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/olimar.png'),
(1298, 'Lucario', 'lucario', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/lucario.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/lucario.png'),
(1323, 'R.O.B.', 'rob', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/rob.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/rob.png'),
(1333, 'Toon Link', 'toon_link', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/toon_link.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/toon_link.png'),
(1337, 'Wolf', 'wolf', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/wolf.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/wolf.png'),
(1334, 'Villager', 'villager', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/villager.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/villager.png'),
(1305, 'Mega Man', 'mega_man', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/mega_man.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/mega_man.png'),
(1336, 'Wii Fit Trainer', 'wii_fit_trainer', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/wii_fit_trainer.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/wii_fit_trainer.png'),
(1325, 'Rosalina & Luma', 'rosalina_and_luma', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/rosalina_and_luma.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/rosalina_and_luma.png'),
(1297, 'Little Mac', 'little_mac', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/little_mac.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/little_mac.png'),
(1289, 'Greninja', 'greninja', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/greninja.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/greninja.png'),
(1311, 'Mii Brawler', 'mii_brawler', './assets/characters/mii_brawler-icon.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/mii_brawler.png'),
(1414, 'Mii Swordfighter', 'mii_swordfighter', './assets/characters/mii_swordfighter-icon.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/mii_swordfighter.png'),
(1415, 'Mii Gunner', 'mii_gunner', './assets/characters/mii_gunner-icon.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/mii_gunner.png'),
(1316, 'Palutena', 'palutena', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/palutena.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/palutena.png'),
(1315, 'Pac-Man', 'pac_man', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/pac_man.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/pac_man.png'),
(1324, 'Robin', 'robin', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/robin.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/robin.png'),
(1330, 'Shulk', 'shulk', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/shulk.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/shulk.png'),
(1272, 'Bowser Jr.', 'bowser_jr', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/bowser_jr.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/bowser_jr.png'),
(1283, 'Duck Hunt Duo', 'duck_hunt', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/duck_hunt.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/duck_hunt.png'),
(1327, 'Ryu', 'ryu', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/ryu.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/ryu.png'),
(1275, 'Cloud', 'cloud', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/cloud.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/cloud.png'),
(1276, 'Corrin', 'corrin', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/corrin.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/corrin.png'),
(1271, 'Bayonetta', 'bayonetta', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/bayonetta.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/bayonetta.png'),
(1292, 'Inkling', 'inkling', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/inkling.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/inkling.png'),
(1322, 'Ridley', 'ridley', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/ridley.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/ridley.png'),
(1411, 'Simon', 'simon', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/simon.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/simon.png'),
(1407, 'King K. Rool', 'king_k_rool', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/king_k_rool.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/king_k_rool.png'),
(1413, 'Isabelle', 'isabelle', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/isabelle.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/isabelle.png'),
(1406, 'Incineroar', 'incineroar', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/incineroar.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/incineroar.png'),
(1441, 'Piranha Plant', 'piranha_plant', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/piranha_plant.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/piranha_plant.png'),
(1453, 'Joker', 'joker', './assets/characters/joker-icon.png', './assets/characters/joker-portrait.png'),
(1526, 'Hero', 'dq_hero', './assets/characters/dq_hero-icon.png', './assets/characters/dq_hero-portrait.png'),
(1530, 'Banjo & Kazooie', 'banjo_and_kazooie', './assets/characters/banjo_and_kazooie-icon.png', './assets/characters/banjo_and_kazooie-portrait.png'),
(1532, 'Terry', 'terry', './assets/characters/terry-icon.png', './assets/characters/terry-portrait.png'),
(1539, 'Byleth', 'byleth', './assets/characters/byleth-icon.png', './assets/characters/byleth-portrait.png'),
(1747, 'Min Min', 'minmin', './assets/characters/minmin-icon.png', './assets/characters/minmin-portrait.png'),
(1766, 'Steve', 'steve', './assets/characters/steve-icon.png', './assets/characters/steve-portrait.png'),
(1777, 'Sephiroth', 'sephiroth', './assets/characters/sephiroth-icon.png', './assets/characters/sephiroth-portrait.png'),
(1795, 'Pyra & Mythra', 'pyra', './assets/characters/pyra-icon.png', './assets/characters/pyra-portrait.png'),
(1846, 'Kazuya', 'kazuya', './assets/characters/kazuya-icon.png', './assets/characters/kazuya-portrait.png'),
(1897, 'Sora', 'sora', './assets/characters/sora-icon.png', './assets/characters/sora-portrait.png'),
(1278, 'Dark Pit', 'dark_pit', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/dark_pit.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/dark_pit.png'),
(1300, 'Lucina', 'lucina', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/lucina.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/lucina.png'),
(1277, 'Daisy', 'daisy', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/daisy.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/daisy.png'),
(1409, 'Chrom', 'chrom', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/chrom.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/chrom.png'),
(1408, 'Dark Samus', 'dark_samus', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/dark_samus.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/dark_samus.png'),
(1412, 'Richter', 'richter', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/richter.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/richter.png'),
(1410, 'Ken', 'ken', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/stock-icons/png/ken.png', 'https://raw.githubusercontent.com/marcrd/smash-ultimate-assets/master/portraits/full/ken.png'),
(1746, 'Random Character', 'random', NULL, NULL)
ON DUPLICATE KEY UPDATE name=VALUES(name), slug=VALUES(slug), icon_url=VALUES(icon_url), portrait_url=VALUES(portrait_url);
