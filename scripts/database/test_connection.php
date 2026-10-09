<?php
declare(strict_types=1);
ini_set('display_errors', '0');
require dirname(__DIR__, 2) . '/ranking-smash-ultimate/database.php';

function verify(bool $condition, string $label): void {
    if (!$condition) throw new RuntimeException('Test failed: ' . $label);
}
function rejects(callable $fn, string $reason): void {
    try { $fn(); } catch (SmashDatabaseError $error) {
        verify($error->reason === $reason, $reason);
        return;
    }
    throw new RuntimeException('Expected rejection: ' . $reason);
}

$home = sys_get_temp_dir() . '/smash-db-test-' . bin2hex(random_bytes(8));
$site = $home . '/site';
$private = $home . '/private-smash';
mkdir($site, 0700, true);
mkdir($private, 0700);
$configPath = $private . '/config.local.php';
try {
    verify(smash_admin_session_valid(['smash_admin'=>true,'smash_admin_at'=>100], 101), 'active session');
    foreach ([[], ['smash_admin'=>false,'smash_admin_at'=>100], ['smash_admin'=>true,'smash_admin_at'=>102],
        ['smash_admin'=>true,'smash_admin_at'=>'100'], ['smash_admin'=>true,'smash_admin_at'=>0]] as $session) {
        verify(!smash_admin_session_valid($session, 101), 'invalid session');
    }
    verify(!smash_admin_session_valid(['smash_admin'=>true,'smash_admin_at'=>100], 28900), 'expired session');
    rejects(fn()=>smash_database_config($site), 'config_missing');
    file_put_contents($configPath, "<?php return ['database'=>['host'=>'localhost','port'=>3306,'name'=>'example','user'=>'USUARIO_MYSQL_COMPLETO','password'=>'CONTRASENA_MYSQL']];");
    rejects(fn()=>smash_database_config($site), 'config_incomplete');
    file_put_contents($configPath, '<?php invalid php syntax;');
    rejects(fn()=>smash_database_config($site), 'config_invalid');
    file_put_contents($configPath, 'SECRET-MARKER invalid non-PHP config');
    ob_start();
    rejects(fn()=>smash_database_config($site), 'config_invalid');
    verify(ob_get_clean() === '', 'configuration output must be suppressed');
    $db = ['host'=>'localhost','port'=>3306,'name'=>'example','user'=>'example','password'=>"test-only-$'\\password"];
    file_put_contents($configPath, '<?php return '.var_export(['database'=>$db], true).';');
    verify(smash_database_config($site) === $db, 'special characters preserved');
    $invalid = $db;
    $invalid['name'] = 'example;charset=latin1';
    file_put_contents($configPath, '<?php return '.var_export(['database'=>$invalid], true).';');
    rejects(fn()=>smash_database_config($site), 'config_invalid');
    unlink($configPath);
    file_put_contents($site.'/leak.php', '<?php return '.var_export(['database'=>$db], true).';');
    symlink($site.'/leak.php', $configPath);
    rejects(fn()=>smash_database_config($site), 'config_location_invalid');
    unlink($configPath);
    verify(count(smash_database_expected_tables()) === 31, 'expected schema tables');
    echo "Configuration, privacy and session checks passed.\n";

    if (getenv('SMASH_SCHEMA_TEST_DB')) {
        verify(strpos(getenv('SMASH_SCHEMA_TEST_DB'), 'smash_schema_test') === 0, 'disposable database only');
        $db = ['host'=>'127.0.0.1','port'=>(int)getenv('SMASH_SCHEMA_TEST_PORT'),
            'name'=>getenv('SMASH_SCHEMA_TEST_DB'),'user'=>'root','password'=>getenv('SMASH_SCHEMA_TEST_PASSWORD')];
        $pdo = smash_database_connect($db);
        $status = smash_database_status($pdo);
        verify($status['ok'] && $status['schemaReady'], 'actual database diagnostic');
        verify($status['tableCount'] === 43 && $status['counts']['characters'] === 87, 'installed schema');
        verify($status['migrations'] === ['001_accounts_competition', '002_sessions_visits', '003_visit_networks', '004_premium', '005_organizer_tops', '006_organizer_event_context'], 'installed migrations are reported');
        verify($status['counts']['players'] === 0 && $status['counts']['cuts'] === 0, 'read only, no inserted data');
        verify((bool)$pdo->getAttribute(PDO::ATTR_EMULATE_PREPARES) === false, 'native prepared statements');
        verify($pdo->query('SELECT @@session.time_zone')->fetchColumn() === '+00:00', 'UTC');
        $bad = $db;
        $bad['password'] = 'incorrect-test-only';
        rejects(fn()=>smash_database_connect($bad), 'connection_denied');
        echo "PDO integration and sanitized connection errors passed.\n";
    }
} finally {
    if (file_exists($configPath) || is_link($configPath)) unlink($configPath);
    if (file_exists($site.'/leak.php')) unlink($site.'/leak.php');
    rmdir($site);
    rmdir($private);
    rmdir($home);
}
