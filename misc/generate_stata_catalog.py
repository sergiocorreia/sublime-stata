#!/usr/bin/env python3
"""Generate the bundled completion catalog from an installed Stata tree.

No executable scraper or interactive Stata session is required.  The selection
policy is deliberately reproducible and reviewable:

* documented ado programs require a program declaration and either a
  same-named ``.sthlp`` entry or an official ``*help_alias.maint`` mapping to
  a shared help page that contains syntax markup for that command;
* a checked-in allowlist supplies commands implemented by Stata's executable or
  public dispatchers that do not have a same-named ado program; and
* a checked-in denylist removes the rare private helper that nevertheless has
  its own technical help entry.

``ado/updates`` is layered over ``ado/base`` when present.  Regenerate with
``python3 misc/generate_stata_catalog.py --stata-root /path/to/stata`` and use
``--check`` to verify that the checked-in JSON matches that installation.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Dict, Iterable, Optional, Sequence, Set


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPOSITORY_ROOT / "completions" / "stata19_commands.json"
PROGRAM_DECLARATION = re.compile(
    r"^\s*pr(?:o(?:g(?:r(?:a(?:m)?)?)?)?)?\s+"
    r"(?:def(?:i(?:n(?:e)?)?)?\s+)?([A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
HELPER_SUFFIX = re.compile(
    r"_(?:[0-9]+(?:_[0-9]+)*|p|lf|d[012]|dr|sw|dlg|wrk_dlg|"
    r"parse|parser|util|utils|internal|compute|display|replay|"
    r"predict|prediction|likelihood|dialog|footnote|options|opts|check|"
    r"init|get|post|header|table|stop)$",
    re.IGNORECASE,
)
HELPER_TOKEN = re.compile(
    r"(?:^|_)(?:estat|predict|prediction|likelihood|dialog|dlg|internal|helper)"
    r"(?:_|$)",
    re.IGNORECASE,
)

# Validated user-facing commands that are implemented by Stata itself or routed
# through a public ado dispatcher and are not reliably captured by the strict
# documented-program rules. Keeping the union explicit makes generation
# deterministic, auditable, and immune to the helper-name filters below.
VALIDATED_BUILTIN_OR_DISPATCHER_COMMANDS = {
    "about", "adopath", "args", "assert", "break", "browse", "by", "bysort",
    "capture", "cat", "cd", "char", "class", "clear", "clonevar", "cls",
    "compress", "confirm",
    "constraint", "continue", "copy", "count", "decode", "describe", "di",
    "dir", "discard", "display", "do", "doedit", "drop", "edit", "else", "encode",
    "erase", "error", "ereturn", "estat", "exit", "expand", "file", "filefilter",
    "format",
    "foreach", "forvalues", "fvexpand", "fvrevar",
    "generate", "gettoken", "global", "if", "include", "infile", "infix",
    "input", "inspect", "insheet", "keep", "label", "list", "local", "ls",
    "h2o", "java", "javacall", "macro", "mark", "markin", "markout",
    "marksample", "mat_capp", "mat_order", "mat_rapp", "mata", "matrix",
    "memory", "merge", "mkdir", "mleval", "mlmatsum", "mlsum", "mlvecsum",
    "more", "move", "net", "nobreak", "noisily", "novarabbrev", "numlist", "odbc",
    "oneway", "order", "outfile", "outsheet", "parse", "pause",
    "plugin", "post", "postclose", "postfile", "predict", "preserve", "printer",
    "program", "putdocx",
    "pwd", "python", "quietly", "recast", "rename", "replace", "restore", "return",
    "rm", "rmdir", "run", "save", "scalar", "set", "shell", "sleep", "sort",
    "sreturn",
    "su", "summarize", "sysdir", "syntax", "tab", "tabulate", "tempfile",
    "tempname", "tempvar", "testparm", "tokenize", "tostring", "twoway", "type",
    "update", "use", "version", "view", "while", "window", "winexec", "which",
    "xi", "xtdidregress", "checksum", "cmdlog", "correlate", "creturn",
    "hexdump", "log", "query", "serset", "snapshot", "tabdisp", "timer",
    "translate", "tsrevar", "unabcmd", "varabbrev", "xshell",
}

# Technical help exists for these implementation details, so the general
# declaration+help rule cannot distinguish them from user-facing commands.
DENIED_ADO_COMMANDS = {
    "checkdlgfiles",
    "checkhlpfiles",
    "cscript_log",
    "disp_res",
    "dtaversion",
    "gphpen",
    "twoway__function_gen",
    "twoway__histogram_gen",
    "twoway__kdensity_gen",
}

# Some dispatcher/native commands intentionally do not have a same-named help
# file or a simple first ``program`` declaration.  Keep this small list explicit
# so new Stata features remain guaranteed even if Stata changes its packaging.
GUARANTEED_MODERN_COMMANDS = {
    "bayes", "bma", "collect", "dtable", "etable", "export", "finregress",
    "frame", "frames", "hdidregress", "import", "lasso",
    "lateffects", "mediate", "meta", "python", "xtswitchdid",
}


def stata_version(stata_root: Path) -> str:
    markers = list(stata_root.glob("isstata.*")) + list(stata_root.glob("installed.*"))
    versions = []
    for marker in markers:
        suffix = marker.suffix.lstrip(".")
        if suffix.isdigit() and len(suffix) >= 2:
            versions.append(suffix)
    if not versions:
        raise ValueError("Could not infer Stata version from isstata.* or installed.*")
    encoded = max(versions, key=int)
    return encoded[:-1] + "." + encoded[-1]


def update_date(stata_root: Path) -> str:
    candidates = [stata_root / "ado" / "base" / "update", stata_root / "utilities" / "update"]
    for path in candidates:
        try:
            value = path.read_text(encoding="ascii").strip().splitlines()[0]
            return datetime.strptime(value, "%d %b %Y").date().isoformat()
        except (OSError, ValueError, IndexError):
            continue
    raise ValueError("Could not read the Stata update date")


def first_program(path: Path) -> Optional[str]:
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for index, line in enumerate(handle):
                match = PROGRAM_DECLARATION.match(line)
                if match:
                    return match.group(1).lower()
                if index >= 249:
                    break
    except OSError:
        return None
    return None


def ado_programs(ado_roots: Sequence[Path]) -> Set[str]:
    programs = set()
    for path in sorted(path for root in ado_roots for path in root.rglob("*.ado")):
        command = first_program(path)
        if command and not command.startswith("_"):
            programs.add(command)
    return programs


def help_stems(ado_roots: Sequence[Path]) -> Set[str]:
    return {
        path.stem.lower()
        for root in ado_roots
        for path in root.rglob("*.sthlp")
        if not path.stem.startswith("_")
    }


def shared_help_commands(ado_roots: Sequence[Path], programs: Set[str]) -> Set[str]:
    """Find public programs documented within another command's help page.

    Stata's installed ``*help_alias.maint`` files map names such as ``pwcorr``
    and ``avplot`` to shared help pages. Requiring explicit command/option
    syntax markup on the target page avoids treating every topic alias or
    legal command abbreviation as a standalone completion.
    """

    help_files = {}
    aliases = {}
    for root in ado_roots:
        for path in root.rglob("*.sthlp"):
            help_files[path.stem.lower()] = path
        for path in root.rglob("*help_alias.maint"):
            try:
                lines = path.read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()
            except OSError:
                continue
            for line in lines:
                if not line.strip() or line.lstrip().startswith("*"):
                    continue
                fields = line.split()
                if len(fields) >= 2:
                    aliases[fields[0].lower()] = fields[1].lower()

    documented = set()
    for command in programs:
        # Underscored names in the installed ado tree are implementation
        # dispatchers. Any public underscored commands are retained explicitly
        # in the reviewed allowlists below.
        if "_" in command:
            continue
        target = aliases.get(command)
        if (
            target
            and target != command
            and target.startswith(command)
            and target[len(command):len(command) + 1] != "_"
        ):
            # Stata accepts unambiguous abbreviations, and many of those have
            # help aliases. Keep the small preferred-alias set in the explicit
            # allowlist instead of flooding completion with every prefix.
            continue
        help_path = help_files.get(target or "")
        if help_path is None:
            continue
        try:
            contents = help_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        command_markup = re.compile(
            r"\{(?:cmd|opt)(?::|\s+)\s*"
            + re.escape(command)
            + r"(?=[\s,}:])",
            re.IGNORECASE,
        )
        if command_markup.search(contents):
            documented.add(command)
    return documented


def public_ado_commands(ado_roots: Sequence[Path]) -> Set[str]:
    """Return documented ado commands while excluding implementation helpers."""

    programs = ado_programs(ado_roots)
    documented = help_stems(ado_roots) | shared_help_commands(ado_roots, programs)
    return {
        command
        for command in programs
        if command in documented
        and "_" not in command
        and not HELPER_SUFFIX.search(command)
        and not HELPER_TOKEN.search(command)
        and command not in DENIED_ADO_COMMANDS
        and "__" not in command
    }


def build_catalog(stata_root: Path) -> Dict[str, object]:
    base = stata_root / "ado" / "base"
    if not base.is_dir():
        raise ValueError("Expected an installed Stata ado/base directory")
    updates = stata_root / "ado" / "updates"
    ado_roots = [base]
    if updates.is_dir():
        ado_roots.append(updates)
    ado = public_ado_commands(ado_roots)
    commands = sorted(
        ado | VALIDATED_BUILTIN_OR_DISPATCHER_COMMANDS | GUARANTEED_MODERN_COMMANDS,
        key=str.casefold,
    )
    return {
        "schema_version": 1,
        "stata": {
            "version": stata_version(stata_root),
            "update_date": update_date(stata_root),
            "edition": "StataNow",
            "platform": "linux-x86_64",
        },
        "sources": {
            "public_ado_commands": len(ado),
            "validated_builtin_or_dispatcher_commands": len(
                VALIDATED_BUILTIN_OR_DISPATCHER_COMMANDS
            ),
            "guaranteed_modern_commands": len(GUARANTEED_MODERN_COMMANDS),
            "denied_ado_commands": len(DENIED_ADO_COMMANDS),
            "scanned_updates": updates.is_dir(),
        },
        "commands": commands,
    }


def rendered_catalog(payload: Dict[str, object]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Regenerate the documented/native Stata command catalog.",
        epilog=(
            "Public ado commands require program and direct/shared help evidence; "
            "checked-in native and deny lists cover executable dispatchers and "
            "documented implementation helpers."
        ),
    )
    parser.add_argument(
        "--stata-root",
        type=Path,
        default=Path("/usr/local/stata19"),
        help="Installed Stata directory containing ado/base",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit nonzero if the checked-in catalog is not reproducible",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    try:
        rendered = rendered_catalog(build_catalog(args.stata_root.resolve()))
    except ValueError as error:
        print("error: {}".format(error), file=sys.stderr)
        return 2

    if args.check:
        try:
            current = args.output.read_text(encoding="utf-8")
        except OSError:
            current = ""
        if current != rendered:
            print("catalog is out of date: {}".format(args.output), file=sys.stderr)
            return 1
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print("wrote {} commands to {}".format(len(json.loads(rendered)["commands"]), args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
