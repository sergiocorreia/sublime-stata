#!/usr/bin/env python3
"""Distill a private command-count CSV into public command-name tiers."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "extra" / "cmd_count.csv"
DEFAULT_OUTPUT = ROOT / "completions" / "command_tiers.json"
COMMAND_CATALOG = ROOT / "completions" / "stata19_commands.json"

VERY_COMMON_MIN_SHARE = 0.40
COMMON_MIN_SHARE = 0.10

ALIASES = {
    "di": "display",
    "disp": "display",
    "forval": "forvalues",
    "g": "generate",
    "ge": "generate",
    "gen": "generate",
    "la": "label",
    "lab": "label",
    "loc": "local",
    "mat": "matrix",
    "reg": "regress",
    "ren": "rename",
    "su": "summarize",
    "sum": "summarize",
    "summ": "summarize",
    "tab": "tabulate",
    "u": "use",
}

# These commands are commonly installed by researchers and can be discovered
# from project/personal ado directories even though they are not official base
# catalog entries.
COMMUNITY_COMMANDS = {
    "coefplot", "estadd", "eststo", "esttab", "gcollapse", "gegen",
    "gisid", "ivreg2", "outreg2", "ppmlhdfe", "rangestat", "reghdfe",
    "winsor2",
}


def build_tiers(input_path: Path) -> dict:
    with COMMAND_CATALOG.open(encoding="utf-8") as handle:
        official = {command.lower() for command in json.load(handle)["commands"]}
    allowed = official | COMMUNITY_COMMANDS
    scores: dict[str, float] = {}

    with input_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"cmd", "share_projects"}
        if not required <= set(reader.fieldnames or ()):
            raise ValueError("Input must contain cmd and share_projects columns")
        for row in reader:
            command = row["cmd"].strip().lower()
            if not re.fullmatch(r"[a-z][a-z0-9_]*", command):
                continue
            canonical = ALIASES.get(command, command)
            share = float(row["share_projects"])
            for name in {command, canonical}:
                if name in allowed:
                    scores[name] = max(scores.get(name, 0.0), share)

    very_common = sorted(
        command for command, share in scores.items()
        if share >= VERY_COMMON_MIN_SHARE
    )
    common = sorted(
        command for command, share in scores.items()
        if COMMON_MIN_SHARE <= share < VERY_COMMON_MIN_SHARE
    )
    return {
        "schema_version": 1,
        "methodology": {
            "primary_signal": "share of projects using the command",
            "very_common_min_share": VERY_COMMON_MIN_SHARE,
            "common_min_share": COMMON_MIN_SHARE,
            "counts_included": False,
            "unlisted_commands": "infrequent/default tier",
        },
        "tiers": {
            "very_common": very_common,
            "common": common,
        },
    }


def serialized(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    expected = serialized(build_tiers(args.input))
    if args.check:
        return 0 if args.output.exists() and args.output.read_text(encoding="utf-8") == expected else 1
    args.output.write_text(expected, encoding="utf-8")
    print("wrote {}".format(args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
