-- Smash GT migración 004: suscripciones premium (Recurrente).
-- Ejecutar UNA vez sobre la base con las migraciones 002 y 003. Solo crea tablas; repetirla no cambia nada.
SET NAMES utf8mb4;
SET time_zone = '+00:00';

-- Una fila por intento de suscripción de una cuenta. Solo identificadores de Recurrente y estado:
-- nunca tarjeta, nombre, correo, teléfono ni NIT del pagador.
CREATE TABLE IF NOT EXISTS premium_subscriptions (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, user_id BIGINT UNSIGNED NOT NULL,
 plan ENUM('monthly','annual') NOT NULL, live_mode TINYINT(1) NOT NULL,
 provider_checkout_id VARCHAR(80) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 provider_subscription_id VARCHAR(80) CHARACTER SET ascii COLLATE ascii_bin NULL,
 status ENUM('pending','active','past_due','canceled','ended') NOT NULL DEFAULT 'pending',
 current_period_end DATETIME(6) NULL, cancel_requested_at DATETIME(6) NULL,
 created_at DATETIME(6) NOT NULL, updated_at DATETIME(6) NOT NULL,
 UNIQUE KEY uq_premium_checkout (provider_checkout_id), UNIQUE KEY uq_premium_subscription (provider_subscription_id),
 KEY idx_premium_user (user_id, live_mode, status),
 CONSTRAINT fk_premium_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Avisos de Recurrente ya recibidos, para no procesar dos veces el mismo. Sin contenido del aviso.
CREATE TABLE IF NOT EXISTS premium_events (
 event_id VARCHAR(120) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 event_type VARCHAR(80) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 outcome VARCHAR(40) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 received_at DATETIME(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO schema_migrations (version) VALUES ('004_premium');
