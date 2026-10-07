-- Smash GT migración 003: conteo de visitas por red.
-- Ejecutar UNA vez sobre la base con la migración 002. Solo crea una tabla; repetirla no cambia nada.
SET NAMES utf8mb4;
SET time_zone = '+00:00';

-- Una fila por día y por red. network_hash es un HMAC de la IP con una clave privada del
-- servidor (uso de la IP autorizado por el dueño el 7/oct/2026); la IP nunca se guarda.
-- new_visitors limita cuántos identificadores de visitante nuevos acepta una red en un día.
CREATE TABLE IF NOT EXISTS site_network_days (
 day DATE NOT NULL, network_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 views INT UNSIGNED NOT NULL DEFAULT 0, new_visitors INT UNSIGNED NOT NULL DEFAULT 0,
 PRIMARY KEY (day, network_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO schema_migrations (version) VALUES ('003_visit_networks');
