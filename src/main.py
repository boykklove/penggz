from __future__ import annotations

import argparse
import json
from pathlib import Path

from adapters.mgz_cli import extract_summary_from_rec
from core.exporters import export_match_summary, export_timeline_csv
from core.normalize import normalize_summary


def _load_summary_from_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("summary JSON must be a JSON object")
    return data


def run_analyze(rec: Path | None, summary_json: Path | None, out_dir: Path) -> None:
    if bool(rec) == bool(summary_json):
        raise ValueError("Specify exactly one of --rec or --summary-json")

    if rec:
        raw = extract_summary_from_rec(rec)
    else:
        raw = _load_summary_from_json(summary_json)  # type: ignore[arg-type]

    summary = normalize_summary(raw)
    summary_path = export_match_summary(summary, out_dir)
    timeline_path = export_timeline_csv(summary, out_dir)

    print(f"Wrote: {summary_path}")
    print(f"Wrote: {timeline_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AoE2 Conquerors replay analyzer")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="Analyze one replay")
    analyze.add_argument("--rec", type=Path, default=None, help="Path to .mgz/.mgl replay")
    analyze.add_argument("--summary-json", type=Path, default=None, help="Pre-exported summary JSON")
    analyze.add_argument("--out", type=Path, default=Path("out"), help="Output directory")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "analyze":
        run_analyze(args.rec, args.summary_json, args.out)


if __name__ == "__main__":
    main()
