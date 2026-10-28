#!/usr/bin/env bash
# Manual, only for the owner's cPanel Terminal. No HTTP, SQL, cron or deployment.
set +x
set -euo pipefail
umask 077
smash_ig_php=/usr/local/bin/php
smash_ig_target=/home/ivcjgjlk/private-smash/instagram.local.php
smash_ig_account_id=17841423954542472
trap 'unset smash_ig_token' EXIT
if [[ ! -x "$smash_ig_php" ]]; then
  echo 'No está disponible /usr/local/bin/php. Compartí solo la ruta PHP del cron actual.' >&2
  exit 1
fi
if [[ -e "$smash_ig_target" || -L "$smash_ig_target" ]]; then
  echo 'La configuración ya existe. Se conserva sin cambios; no pegues otra llave.' >&2
  exit 1
fi
"$smash_ig_php" -d display_errors=0 -d log_errors=0 -r '
$ok=PHP_SAPI==="cli" && PHP_VERSION_ID>=80100 && extension_loaded("curl") && extension_loaded("gd") && extension_loaded("mbstring");
echo $ok ? "PHP y extensiones: correctos.\n" : "Falta PHP CLI 8.1+, curl, GD o mbstring. No se guardó nada.\n";
exit($ok ? 0 : 1);'
read -r -p '¿Es un token LARGO de 60 días generado en las últimas 24 horas? Escribí SI: ' smash_ig_fresh </dev/tty
if [[ "$smash_ig_fresh" != SI ]]; then
  echo 'Configuración cancelada. Primero confirma la duración en Meta; no se guardó nada.'
  exit 0
fi
read -r -s -p 'Pegá el token de Instagram (no se mostrará) y presioná Enter: ' smash_ig_token </dev/tty
printf '\n' >/dev/tty
# printf is a Bash builtin: the secret travels through stdin, never an argv or file in Git.
printf '%s' "$smash_ig_token" | "$smash_ig_php" -d display_errors=0 -d log_errors=0 -r '
umask(0077);
$path=$argv[1];$account=$argv[2];$handle=null;$created=false;
set_error_handler(static function(){throw new RuntimeException("setup_failed");});
try {
  $token=stream_get_contents(STDIN,4097);
  if(!is_string($token) || preg_match("/^[\\x21-\\x7e]{20,4096}$/D",$token)!==1)throw new RuntimeException("setup_failed");
  $dir=dirname($path);
  if(!is_dir($dir) && !mkdir($dir,0700))throw new RuntimeException("setup_failed");
  if(realpath($dir)!==$dir || is_link($path) || file_exists($path))throw new RuntimeException("setup_failed");
  // A lower bound, not a claim to know Meta issue time: valid only for the fresh long token confirmed above.
  // Expiration is conservatively one day earlier; first refresh is still at least six days after setup.
  $config=["enabled"=>false,"account_id"=>$account,"access_token"=>$token,"issued_at"=>gmdate("Y-m-d\\TH:i:s\\Z",time()-86400)];
  $body="<?php\nreturn ".var_export($config,true).";\n";
  $handle=fopen($path,"x");
  if($handle===false)throw new RuntimeException("setup_failed");
  $created=true;
  if(!chmod($path,0600) || fwrite($handle,$body)!==strlen($body) || !fflush($handle))throw new RuntimeException("setup_failed");
  fclose($handle);$handle=null;
  echo "Configuración privada guardada (600). Captura DESACTIVADA; no se creó ningún cron.\n";
} catch(Throwable $error) {
  if(is_resource($handle))fclose($handle);
  if($created && is_file($path))@unlink($path);
  fwrite(STDERR,"No se pudo guardar la configuración privada. No compartas la llave; comparte solo este mensaje.\n");
  exit(1);
}' -- "$smash_ig_target" "$smash_ig_account_id"
unset smash_ig_token
