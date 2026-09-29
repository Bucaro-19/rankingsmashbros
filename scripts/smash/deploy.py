"""Publica solo los archivos de Smash GT; sustituye cada archivo al terminar su subida."""
import ftplib
import json
import os
import ssl
import uuid
from pathlib import Path

FILES = ("style.css", "arena.css", "app.js", ".htaccess", "index.html", "data/public.json")


def validate_public_data(data):
    counts = data.get("counts") or {}
    players = data.get("players")
    if (data.get("schemaVersion") != 2 or data.get("status") != "international_pilot"
            or data.get("rankingComputed") is not True or not isinstance(players, list)
            or len(players) != 100 or counts.get("players") != 100
            or not isinstance(counts.get("events"), int) or counts["events"] < 1
            or not isinstance(counts.get("sets"), int) or counts["sets"] < 1):
        raise ValueError("Se requiere un top 100 piloto completo con eventos internacionales antes de publicar.")


def deploy(ftp, source):
    # FTP credentials must have the same root as the existing portfolio workflow.
    # No deletion or recursive synchronization of the site's root.
    try:
        ftp.cwd("ranking-smash-ultimate")
    except ftplib.error_perm as error:
        if not str(error).startswith("550"):
            raise
        ftp.mkd("ranking-smash-ultimate")
        ftp.cwd("ranking-smash-ultimate")
    try:
        ftp.cwd("data")
    except ftplib.error_perm as error:
        if not str(error).startswith("550"):
            raise
        ftp.mkd("data")
        ftp.cwd("data")
    ftp.cwd("..")
    for name in FILES:
        temporary = name + "." + uuid.uuid4().hex + ".tmp"
        try:
            with (source / name).open("rb") as file:
                ftp.storbinary("STOR " + temporary, file)
            ftp.rename(temporary, name)
        except Exception:
            try:
                ftp.delete(temporary)
            except ftplib.all_errors:
                pass
            raise


def main():
    source = Path(__file__).resolve().parents[2] / "ranking-smash-ultimate"
    data = json.loads((source / "data/public.json").read_text())
    try:
        validate_public_data(data)
    except ValueError as error:
        raise SystemExit(str(error)) from None
    for name in FILES:
        if not (source / name).is_file():
            raise SystemExit("Faltan archivos de publicación.")
    required = ("FTP_SERVER", "FTP_USERNAME", "FTP_PASSWORD")
    if not all(os.environ.get(name) for name in required):
        raise SystemExit("Faltan secretos de publicación.")
    try:
        with ftplib.FTP_TLS(context=ssl.create_default_context(), timeout=45) as ftp:
            ftp.connect(os.environ["FTP_SERVER"], 21)
            ftp.login(os.environ["FTP_USERNAME"], os.environ["FTP_PASSWORD"])
            ftp.prot_p()
            deploy(ftp, source)
            ftp.quit()
    except (ftplib.Error, OSError, EOFError):
        raise SystemExit("Publicación incompleta. Comprobar FTPS, certificado y permisos de la carpeta. No se eliminó el contenido anterior.") from None
    print("Smash GT publicado en su subcarpeta; datos reemplazados después de completar la subida.")


if __name__ == "__main__":
    main()
