-- Smash GT migración 005: tops por organizador.
-- Ejecutar UNA vez sobre la base con las migraciones 002 a 004. Solo crea tablas; repetirla no cambia nada.
SET NAMES utf8mb4;
SET time_zone = '+00:00';

-- Catálogo de la captura semanal: cada evento de Ultimate de los torneos de Guatemala, también los que
-- el ranking excluye, con quién creó el torneo en start.gg. `reason` es el motivo de exclusión que dio
-- la captura (NULL si el evento se capturó). Sin llave a `tournaments`: esa tabla solo tiene los capturados.
CREATE TABLE IF NOT EXISTS tournament_catalog (
 tournament_id BIGINT UNSIGNED NOT NULL, event_id BIGINT UNSIGNED NOT NULL,
 owner_startgg_user_id BIGINT UNSIGNED NULL,
 tournament_name VARCHAR(255) NOT NULL, slug VARCHAR(255) CHARACTER SET ascii COLLATE ascii_bin NULL,
 starts_at DATETIME(6) NULL, city VARCHAR(120) NULL,
 event_name VARCHAR(255) NULL, entrants INT UNSIGNED NULL,
 reason VARCHAR(40) CHARACTER SET ascii COLLATE ascii_bin NULL,
 captured_at DATETIME(6) NOT NULL,
 PRIMARY KEY (tournament_id, event_id),
 KEY idx_catalog_owner (owner_startgg_user_id, starts_at), KEY idx_catalog_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Lo que el organizador decide sobre su top: dirección pública estable, si está compartida y su tamaño.
CREATE TABLE IF NOT EXISTS organizer_profiles (
 user_id BIGINT UNSIGNED PRIMARY KEY,
 slug VARCHAR(60) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 public_enabled TINYINT(1) NOT NULL DEFAULT 0, top_size TINYINT UNSIGNED NOT NULL DEFAULT 15,
 created_at DATETIME(6) NOT NULL, updated_at DATETIME(6) NOT NULL,
 UNIQUE KEY uq_organizer_slug (slug),
 CONSTRAINT fk_organizer_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
 CONSTRAINT ck_organizer_size CHECK (top_size IN (5, 10, 15))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Coorganizadores que el organizador agregó: ven su top. No da permisos en start.gg.
CREATE TABLE IF NOT EXISTS organizer_members (
 organizer_user_id BIGINT UNSIGNED NOT NULL, member_user_id BIGINT UNSIGNED NOT NULL,
 created_at DATETIME(6) NOT NULL,
 PRIMARY KEY (organizer_user_id, member_user_id), KEY idx_organizer_member (member_user_id),
 CONSTRAINT fk_member_organizer FOREIGN KEY (organizer_user_id) REFERENCES users(id) ON DELETE CASCADE,
 CONSTRAINT fk_member_user FOREIGN KEY (member_user_id) REFERENCES users(id) ON DELETE CASCADE,
 CONSTRAINT ck_member_distinct CHECK (organizer_user_id <> member_user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Invitación de un solo uso para sumar un coorganizador. Solo se guarda el hash del código.
CREATE TABLE IF NOT EXISTS organizer_invites (
 token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 organizer_user_id BIGINT UNSIGNED NOT NULL, created_at DATETIME(6) NOT NULL, expires_at DATETIME(6) NOT NULL,
 KEY idx_invite_organizer (organizer_user_id),
 CONSTRAINT fk_invite_organizer FOREIGN KEY (organizer_user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- «Pedir revisión»: un torneo que start.gg registra a nombre de otra cuenta. Lo resuelve el dueño del sitio a mano.
CREATE TABLE IF NOT EXISTS organizer_claims (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 organizer_user_id BIGINT UNSIGNED NOT NULL, requested_by BIGINT UNSIGNED NULL,
 tournament_slug VARCHAR(255) CHARACTER SET ascii COLLATE ascii_bin NOT NULL, tournament_id BIGINT UNSIGNED NULL,
 status ENUM('sent','approved','rejected') NOT NULL DEFAULT 'sent', message VARCHAR(255) NULL,
 created_at DATETIME(6) NOT NULL, resolved_at DATETIME(6) NULL, resolved_by BIGINT UNSIGNED NULL,
 UNIQUE KEY uq_claim (organizer_user_id, tournament_slug), KEY idx_claim_status (status, created_at),
 CONSTRAINT fk_claim_organizer FOREIGN KEY (organizer_user_id) REFERENCES users(id) ON DELETE CASCADE,
 CONSTRAINT fk_claim_requester FOREIGN KEY (requested_by) REFERENCES users(id) ON DELETE SET NULL,
 CONSTRAINT fk_claim_resolver FOREIGN KEY (resolved_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO schema_migrations (version) VALUES ('005_organizer_tops');
