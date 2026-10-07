-- Smash GT migración 002: sesiones persistentes y conteo de visitas.
-- Ejecutar UNA vez en phpMyAdmin sobre la base ya instalada (001_accounts_competition).
-- Solo crea tablas nuevas; no modifica ni borra datos existentes. Repetirla no cambia nada.
SET NAMES utf8mb4;
SET time_zone = '+00:00';

-- «Mantener la sesión iniciada». Se guarda el SHA-256 de un identificador aleatorio propio del
-- sitio, nunca el valor de la cookie, ni tokens de start.gg, IP o navegador.
CREATE TABLE IF NOT EXISTS user_sessions (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, user_id BIGINT UNSIGNED NOT NULL,
 token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 connection_version DATETIME(6) NOT NULL,
 profile_url VARCHAR(512) NULL, avatar_url VARCHAR(512) NULL,
 created_at DATETIME(6) NOT NULL, last_used_at DATETIME(6) NOT NULL, expires_at DATETIME(6) NOT NULL,
 revoked_at DATETIME(6) NULL,
 UNIQUE KEY uq_user_sessions_token (token_hash), KEY idx_user_sessions_user (user_id, expires_at),
 CONSTRAINT fk_user_sessions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Vistas de página por día de Guatemala y por página conocida del sitio.
CREATE TABLE IF NOT EXISTS site_visit_days (
 day DATE NOT NULL, page VARCHAR(40) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 views INT UNSIGNED NOT NULL DEFAULT 0,
 PRIMARY KEY (day, page)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Visitantes distintos por día. visitor_hash es el SHA-256 de un identificador aleatorio guardado
-- en una cookie propia del sitio (autorizado por el dueño el 7/oct/2026). Sin IP ni navegador.
CREATE TABLE IF NOT EXISTS site_visitor_days (
 day DATE NOT NULL, visitor_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 views INT UNSIGNED NOT NULL DEFAULT 0, signed_in TINYINT(1) NOT NULL DEFAULT 0,
 PRIMARY KEY (day, visitor_hash), KEY idx_site_visitor_hash (visitor_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO schema_migrations (version) VALUES ('002_sessions_visits');
