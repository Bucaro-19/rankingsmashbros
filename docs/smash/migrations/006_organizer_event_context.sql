-- Private readiness marker for complete small-event context. Never national cut membership.
-- No ranking rule/minimum decided here. Do NOT apply to production without owner's order.
SET NAMES utf8mb4;
SET time_zone = '+00:00';
CREATE TABLE IF NOT EXISTS organizer_event_context (
 event_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
 cut_id BIGINT UNSIGNED NOT NULL,
 captured_at DATETIME(6) NOT NULL,
 active_players INT UNSIGNED NOT NULL,
 valid_sets INT UNSIGNED NOT NULL,
 context_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 KEY idx_org_context_cut (cut_id),
 CONSTRAINT fk_org_context_event FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
 CONSTRAINT fk_org_context_cut FOREIGN KEY (cut_id) REFERENCES cuts(id) ON DELETE CASCADE,
 CONSTRAINT ck_org_context_activity CHECK (active_players >= 2 AND valid_sets >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT IGNORE INTO schema_migrations (version) VALUES ('006_organizer_event_context');
