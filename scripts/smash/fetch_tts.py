"""Fetch a pinned public UltRank player-points table for reproducible pilot builds."""
import urllib.request
from pathlib import Path

from tiering import SOURCE_URL


def main():
    with urllib.request.urlopen(SOURCE_URL, timeout=30) as response:
        data = response.read(5_000_001)
    if len(data) > 5_000_000 or not data.startswith(b"Category,Note,Player,Start.gg Hex ID,Start.gg Num ID,Points,"):
        raise ValueError("La tabla de puntos TTS no tiene el formato esperado.")
    target = Path(__file__).parent / "data" / "ultrank_players.csv"
    target.parent.mkdir(exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_bytes(data)
    temporary.replace(target)
    print(f"Tabla TTS descargada de la revisión fijada ({len(data)} bytes).")


if __name__ == "__main__":
    main()
