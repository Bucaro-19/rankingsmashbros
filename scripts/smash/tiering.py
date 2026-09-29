"""Estimate Guatemala event points using public UltRank TTS values, not player ranks."""
import csv
import io
from collections import defaultdict
from datetime import date, datetime, timezone

# Public TTS documentation and kenniky's open tierer define entrant points.
# The derived estimate remains provisional because DQ and editorial exclusions
# cannot be fully reconstructed from start.gg alone.
MIDPOINT_DEPRECIATION = {300: 250, 250: 200, 200: 150, 150: 100,
                         100: 50, 50: 30, 30: 30, 0: 0}
SOURCE_COMMIT = "61eaa8828eff709ffbfbabeefdaf062dac48095e"
SOURCE_URL = f"https://raw.githubusercontent.com/kenniky/ultrank-scoring/{SOURCE_COMMIT}/ultrank_players.csv"


def parse_values(csv_text):
    result = defaultdict(list)
    for row in csv.DictReader(io.StringIO(csv_text)):
        try:
            pid = str(int(row["Start.gg Num ID"]))
            points = int(row["Points"])
            start = date.fromisoformat(row["Start Date"]) if row["Start Date"] else None
            end = date.fromisoformat(row["End Date"]) if row["End Date"] else None
            mid = date.fromisoformat(row["Midpt Date"]) if row["Midpt Date"] else None
        except (KeyError, ValueError):
            continue
        if mid is not None and points not in MIDPOINT_DEPRECIATION:
            raise ValueError("Valor de depreciación desconocido en la tabla TTS.")
        result[pid].append((start, mid or end, points))
        if mid is not None:
            result[pid].append((mid, end, MIDPOINT_DEPRECIATION[points]))
    return result


def value_at(entries, timestamp):
    day = datetime.fromtimestamp(timestamp, timezone.utc).date()
    return max((points for start, end, points in entries
                if (start is None or start <= day) and (end is None or day < end)), default=0)


def guatemala_points(active_player_ids, timestamp, values):
    count = len(active_player_ids)
    # 2026 Guatemala is x3, with the 2024-12-16 capped multiplier system.
    entrant_points = count + min(256, count) + min(128, count)
    player_points = sum(value_at(values.get(pid, ()), timestamp) for pid in active_player_ids)
    return entrant_points + player_points
