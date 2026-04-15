from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class Player:
    name: str
    civ: str = "unknown"


@dataclass
class MatchSummary:
    match_id: str
    duration_sec: int
    map_name: str
    players: list[Player]
    milestones: dict[str, dict[str, int]]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["players"] = [asdict(player) for player in self.players]
        return result
