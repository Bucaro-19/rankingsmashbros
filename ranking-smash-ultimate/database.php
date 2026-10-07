<?php
declare(strict_types=1);

// Library only. Apache blocks direct access; no connection is opened on inclusion.
final class SmashDatabaseError extends RuntimeException
{
    public $reason;
    public function __construct(string $reason)
    {
        $this->reason = $reason;
        parent::__construct('No se pudo completar la comprobación de base de datos.');
    }
}

function smash_admin_session_valid(array $session, int $now): bool
{
    $at = $session['smash_admin_at'] ?? null;
    return ($session['smash_admin'] ?? false) === true && is_int($at)
        && $at > 0 && $at <= $now && $now - $at < 8 * 3600;
}

function smash_database_config(string $siteRoot): array
{
    $root = realpath($siteRoot);
    if ($root === false) throw new SmashDatabaseError('config_location_invalid');
    // The confirmed hosting layout has site/ and private-smash/ as siblings.
    // Never take a configuration path from query parameters or scan other folders.
    $expected = dirname($root) . '/private-smash/config.local.php';
    if (!is_file($expected)) throw new SmashDatabaseError('config_missing');
    if (realpath($expected) !== $expected) throw new SmashDatabaseError('config_location_invalid');
    if (!is_readable($expected)) throw new SmashDatabaseError('config_unreadable');
    $level = ob_get_level();
    ob_start();
    try {
        $config = (static function (string $file) { return require $file; })($expected);
    } catch (Throwable $error) {
        // Never return parse errors, paths, file contents, or exception arguments.
        throw new SmashDatabaseError('config_invalid');
    } finally {
        while (ob_get_level() > $level) ob_end_clean();
    }
    if (!is_array($config) || !is_array($config['database'] ?? null)) throw new SmashDatabaseError('config_invalid');
    $db = $config['database'];
    foreach (['host', 'name', 'user', 'password'] as $key) {
        if (!is_string($db[$key] ?? null) || $db[$key] === '') throw new SmashDatabaseError('config_incomplete');
    }
    if ($db['user'] === 'USUARIO_MYSQL_COMPLETO' || $db['password'] === 'CONTRASENA_MYSQL') {
        throw new SmashDatabaseError('config_incomplete');
    }
    if (!preg_match('/\A[A-Za-z0-9_.:-]+\z/D', $db['host'])
        || !preg_match('/\A[A-Za-z0-9_-]+\z/D', $db['name'])
        || strlen($db['user']) > 128 || strlen($db['password']) > 1024
        || !is_int($db['port'] ?? null) || $db['port'] < 1 || $db['port'] > 65535) {
        throw new SmashDatabaseError('config_invalid');
    }
    return $db;
}

function smash_database_connect(array $db): PDO
{
    if (!extension_loaded('pdo_mysql')) throw new SmashDatabaseError('mysql_driver_missing');
    try {
        $pdo = new PDO('mysql:host=' . $db['host'] . ';port=' . $db['port'] . ';dbname=' . $db['name'] . ';charset=utf8mb4',
            $db['user'], $db['password'], [
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_EMULATE_PREPARES => false,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                PDO::ATTR_TIMEOUT => 5,
                // Same option under its current name where it exists (PHP 8.4+), without deprecation notices.
                (defined('Pdo\\Mysql::ATTR_MULTI_STATEMENTS') ? constant('Pdo\\Mysql::ATTR_MULTI_STATEMENTS') : PDO::MYSQL_ATTR_MULTI_STATEMENTS) => false,
            ]);
        $pdo->exec("SET time_zone = '+00:00'");
        return $pdo;
    } catch (PDOException $error) {
        $code = (int)($error->errorInfo[1] ?? 0);
        $reason = [1045 => 'connection_denied', 1044 => 'database_access_denied',
                   1049 => 'database_not_found', 2002 => 'database_unreachable'][ $code ] ?? 'connection_failed';
        throw new SmashDatabaseError($reason);
    }
}

function smash_database_expected_tables(): array
{
    return ['schema_migrations','players','characters','users','user_roles','user_characters','oauth_connections',
        'tournaments','events','tournament_staff','entrants','entrant_players','sets','set_slots','games','game_selections',
        'cuts','cut_events','cut_set_results','rankings','player_characters','result_submissions','result_reviews',
        'result_publish_attempts','audit_log','notification_preferences','push_subscriptions','notifications',
        'notification_deliveries','sync_jobs','survey_responses'];
}

function smash_database_status(PDO $pdo): array
{
    try {
        $rawVersion = (string)$pdo->query('SELECT VERSION()')->fetchColumn();
        $engine = stripos($rawVersion, 'mariadb') !== false ? 'MariaDB' : 'MySQL';
        preg_match('/\A\d+\.\d+\.\d+/', $rawVersion, $matches);
        $version = $matches[0] ?? null;
        $compatible = $version !== null && version_compare($version, $engine === 'MariaDB' ? '10.6.0' : '8.0.16', '>=');
        $tables = $pdo->query("SELECT TABLE_NAME FROM information_schema.tables WHERE table_schema=DATABASE() AND TABLE_TYPE='BASE TABLE'")->fetchAll(PDO::FETCH_COLUMN);
        $missing = array_values(array_diff(smash_database_expected_tables(), $tables));
        $schema = in_array('schema_migrations', $tables, true)
            ? $pdo->query("SELECT version FROM schema_migrations WHERE version='001_accounts_competition'")->fetchColumn() : false;
        // Later migrations add tables without replacing the base version checked above.
        $migrations = in_array('schema_migrations', $tables, true)
            ? array_map('strval', $pdo->query('SELECT version FROM schema_migrations ORDER BY version')->fetchAll(PDO::FETCH_COLUMN)) : [];
        $counts = [];
        // Names are fixed server-side; no request value becomes an SQL identifier.
        foreach (['characters','players','tournaments','events','sets','cuts','rankings','users','survey_responses'] as $table) {
            $counts[$table] = in_array($table, $tables, true) ? (int)$pdo->query('SELECT COUNT(*) FROM `' . $table . '`')->fetchColumn() : null;
        }
        return ['ok' => true, 'connection' => 'connected', 'engine' => $engine, 'version' => $version,
            'schemaVersion' => $schema ?: null, 'migrations' => $migrations, 'tableCount' => count($tables), 'missingTables' => $missing,
            'engineCompatible' => $compatible,
            'schemaReady' => $compatible && !$missing && $schema === '001_accounts_competition' && $counts['characters'] >= 87,
            'counts' => $counts];
    } catch (PDOException $error) {
        throw new SmashDatabaseError('database_read_failed');
    }
}

function smash_database_error_message(string $reason): string
{
    $messages = [
        'config_missing' => 'Falta config.local.php en la carpeta privada indicada.',
        'config_unreadable' => 'PHP no puede leer el archivo privado. Revisa sus permisos.',
        'config_location_invalid' => 'La ubicación del archivo privado no coincide con la estructura del sitio.',
        'config_invalid' => 'Revisa la sintaxis y el formato del archivo privado.',
        'config_incomplete' => 'Completa el usuario y la contraseña MySQL en el archivo privado.',
        'mysql_driver_missing' => 'La extensión pdo_mysql no está disponible en el servidor.',
        'connection_denied' => 'MySQL rechazó el acceso. Revisa el usuario y la contraseña en el servidor.',
        'database_access_denied' => 'El usuario no tiene acceso a la base. Revisa su asociación en cPanel.',
        'database_not_found' => 'No se encontró la base configurada.',
        'database_unreachable' => 'No se pudo contactar MySQL. Revisa el host configurado.',
        'database_read_failed' => 'No se pudo consultar el esquema. Revisa los permisos del usuario MySQL.',
    ];
    return $messages[$reason] ?? 'No se pudo completar la conexión. Revisa la configuración del servidor.';
}
