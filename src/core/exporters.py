from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import MatchSummary


def export_match_summary(summary: MatchSummary, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "match_summary.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(summary.to_dict(), f, ensure_ascii=False, indent=2)
    return path


def export_timeline_csv(summary: MatchSummary, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "timeline.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["player", "event", "time_sec", "time_mmss"])
        for player in summary.players:
            milestones = summary.milestones.get(player.name, {})
            for event, sec in sorted(milestones.items(), key=lambda item: item[1]):
                mmss = f"{sec // 60:02d}:{sec % 60:02d}"
                writer.writerow([player.name, event, sec, mmss])
    return path
