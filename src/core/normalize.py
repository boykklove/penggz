from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import MatchSummary, Player


def _first(source: dict[str, Any], keys: list[str], default: Any = None) -> Any:
    for key in keys:
        if key in source and source[key] is not None:
            return source[key]
    return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _normalize_player(raw: dict[str, Any], index: int) -> Player:
    return Player(
        name=str(_first(raw, ["name", "player_name", "nickname"], default=f"P{index}")),
        civ=str(_first(raw, ["civ", "civilization", "civ_name"], default="unknown")),
    )


def _extract_milestones(raw: dict[str, Any]) -> dict[str, int]:
    milestones = {}
    mapping = {
        "feudal": ["feudal", "feudal_age", "advance_feudal"],
        "castle": ["castle", "castle_age", "advance_castle"],
        "imperial": ["imperial", "imperial_age", "advance_imperial"],
        "barracks": ["barracks", "first_barracks"],
        "archery_range": ["archery_range", "first_archery_range"],
        "stable": ["stable", "first_stable"],
        "town_center": ["town_center", "first_town_center", "tc"],
    }

    for normalized_key, candidates in mapping.items():
        value = _first(raw, candidates)
        if value is not None:
            milestones[normalized_key] = _safe_int(value)
    return milestones


def normalize_summary(raw: dict[str, Any]) -> MatchSummary:
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    match_id = str(_first(raw, ["match_id", "id"], default=now))
    duration_sec = _safe_int(_first(raw, ["duration_sec", "duration", "game_length"], default=0))
    map_name = str(_first(raw, ["map", "map_name"], default="unknown"))

    raw_players = _first(raw, ["players", "player_list"], default=[])
    players: list[Player] = []
    milestones: dict[str, dict[str, int]] = {}

    if isinstance(raw_players, list):
        for i, player_raw in enumerate(raw_players, start=1):
            if not isinstance(player_raw, dict):
                continue
            player = _normalize_player(player_raw, i)
            players.append(player)
            milestones[player.name] = _extract_milestones(player_raw)

    return MatchSummary(
        match_id=match_id,
        duration_sec=duration_sec,
        map_name=map_name,
        players=players,
        milestones=milestones,
    )
