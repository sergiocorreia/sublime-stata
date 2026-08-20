"""Pure, editor-independent completion indexing for Stata source files.

The Sublime listener is deliberately kept thin.  Everything in this module can
be exercised with the system Python and never needs a running Stata process.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import time
from typing import Iterable, List, Optional, Sequence, Set, Tuple


CATALOG_PATH = Path(__file__).with_name("stata19_commands.json")
ADO_CACHE_TTL_SECONDS = 2.0
SOURCE_SUFFIXES = (".do", ".ado", ".doh", ".mata")
IGNORED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".tox",
    ".venv",
    "__pycache__",
    "node_modules",
}

IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_LOCAL_DECLARATION = re.compile(
    r"(?im)^\s*loc(?:al)?\s+(?![+=:-])(" + IDENTIFIER + r"|0)\b"
)
_GLOBAL_DECLARATION = re.compile(
    r"(?im)^\s*glo(?:bal)?\s+(?![+=:-])(" + IDENTIFIER + r")\b"
)
_PROGRAM_DECLARATION = re.compile(
    r"(?im)^\s*pr(?:o(?:g(?:r(?:a(?:m)?)?)?)?)?\s+"
    r"(?:def(?:i(?:n(?:e)?)?)?\s+)?(" + IDENTIFIER + r")\b"
)
_GENERATED_VARIABLE = re.compile(
    r"(?im)^\s*(?:gen(?:erate)?|egen)\s+"
    r"(?:(?:byte|int|long|float|double|str(?:L|[1-9][0-9]*))\s+)?"
    r"(" + IDENTIFIER + r")\b"
)
_CLONED_VARIABLE = re.compile(
    r"(?im)^\s*clonevar\s+(" + IDENTIFIER + r")\b"
)
_RENAMED_VARIABLE = re.compile(
    r"(?im)^\s*rename\s+(?:" + IDENTIFIER + r")\s+(" + IDENTIFIER + r")\b"
)
_INPUT_DECLARATION = re.compile(r"(?im)^\s*input\s+([^/\r\n]+)")
_INPUT_IDENTIFIER = re.compile(
    r"(?:(?:byte|int|long|float|double|str(?:L|[1-9][0-9]*))\s+)?("
    + IDENTIFIER
    + r")\b"
)
_TEMP_DECLARATION = re.compile(
    r"(?im)^\s*temp(var|file|name)\s+([^\r\n]+)"
)
_FRAME_CREATE = re.compile(
    r"(?im)^\s*frame\s+create\s+(" + IDENTIFIER + r")\b([^,\r\n]*)"
)
_FRAME_COPY = re.compile(
    r"(?im)^\s*frame\s+copy\s+" + IDENTIFIER + r"\s+(" + IDENTIFIER + r")\b"
)
_FRAME_RENAME = re.compile(
    r"(?im)^\s*frame\s+rename\s+" + IDENTIFIER + r"\s+(" + IDENTIFIER + r")\b"
)
_FRAME_INTO = re.compile(
    r"(?im)^\s*frame\s+put\b[^\r\n,]*,.*?\binto\s*\(\s*(" + IDENTIFIER + r")\s*\)"
)
_DECLARED_IDENTIFIER = re.compile(r"\b(" + IDENTIFIER + r")\b")
_STORAGE_TYPES = {
    "byte", "int", "long", "float", "double", "strl",
}
_LOCAL_REFERENCE = re.compile(r"`(" + IDENTIFIER + r"|[0-9]+)'", re.MULTILINE)
_GLOBAL_REFERENCE = re.compile(r"\$(?:\{(" + IDENTIFIER + r")\}|(" + IDENTIFIER + r"))")

_PATH_CONTEXT = re.compile(
    r"(?ix)"
    r"(?:"
    r"\b(?:use|save|do|run|include)\b"
    r"|\busing\b"
    r"|\b(?:import|export)\s+(?:delimited|excel|sas|spss|parquet)\b"
    r")"
    r"\s+(?:\"([^\"]*)|([^\s,]*))$"
)
_LOCAL_CONTEXT = re.compile(r"`(" + IDENTIFIER + r"|[A-Za-z_0-9]*)$")
_GLOBAL_CONTEXT = re.compile(r"\$(?:\{)?([A-Za-z_0-9]*)$")
_PREFIX_AT_END = re.compile(
    r"(?ix)^\s*(?:(?:qui(?:etly)?|cap(?:ture)?|noi(?:sily)?|"
    r"no?break|no?varabbrev)\s+)*(" + IDENTIFIER + r")?$"
)


@dataclass(frozen=True)
class SymbolIndex:
    variables: Tuple[str, ...] = ()
    locals: Tuple[str, ...] = ()
    globals: Tuple[str, ...] = ()
    programs: Tuple[str, ...] = ()
    tempvars: Tuple[str, ...] = ()
    tempfiles: Tuple[str, ...] = ()
    tempnames: Tuple[str, ...] = ()
    frames: Tuple[str, ...] = ()

    def merged(self, *others: "SymbolIndex") -> "SymbolIndex":
        return SymbolIndex(
            variables=sorted_union(self.variables, *(item.variables for item in others)),
            locals=sorted_union(self.locals, *(item.locals for item in others)),
            globals=sorted_union(self.globals, *(item.globals for item in others)),
            programs=sorted_union(self.programs, *(item.programs for item in others)),
            tempvars=sorted_union(self.tempvars, *(item.tempvars for item in others)),
            tempfiles=sorted_union(self.tempfiles, *(item.tempfiles for item in others)),
            tempnames=sorted_union(self.tempnames, *(item.tempnames for item in others)),
            frames=sorted_union(self.frames, *(item.frames for item in others)),
        )


@dataclass(frozen=True)
class CompletionContext:
    kind: str
    fragment: str = ""


@dataclass(frozen=True)
class Candidate:
    trigger: str
    completion: str
    annotation: str
    kind: str
    details: str = ""
    snippet: bool = False


def sorted_union(*groups: Iterable[str]) -> Tuple[str, ...]:
    return tuple(sorted({value for group in groups for value in group if value}, key=str.casefold))


@lru_cache(maxsize=4)
def load_command_catalog(path: str = str(CATALOG_PATH)) -> Tuple[str, ...]:
    """Load the generated, deterministic Stata command baseline."""

    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("schema_version") != 1:
        raise ValueError("Unsupported Stata completion catalog schema")
    commands = payload.get("commands")
    if not isinstance(commands, list):
        raise ValueError("Stata completion catalog has no commands list")
    return sorted_union(command for command in commands if isinstance(command, str))


def catalog_metadata(path: str = str(CATALOG_PATH)) -> dict:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    return dict(payload.get("stata", {}))


def extract_symbols(text: str) -> SymbolIndex:
    """Extract declarations and macro references visible in Stata source."""

    variables: Set[str] = set(_GENERATED_VARIABLE.findall(text))
    variables.update(_CLONED_VARIABLE.findall(text))
    variables.update(_RENAMED_VARIABLE.findall(text))
    for declaration in _INPUT_DECLARATION.findall(text):
        variables.update(_INPUT_IDENTIFIER.findall(declaration))

    tempvars: Set[str] = set()
    tempfiles: Set[str] = set()
    tempnames: Set[str] = set()
    temp_groups = {
        "var": tempvars,
        "file": tempfiles,
        "name": tempnames,
    }
    for kind, declaration in _TEMP_DECLARATION.findall(text):
        declaration = re.split(r"//|,", declaration, maxsplit=1)[0]
        temp_groups[kind.lower()].update(_DECLARED_IDENTIFIER.findall(declaration))

    frames: Set[str] = set(_FRAME_COPY.findall(text))
    frames.update(_FRAME_RENAME.findall(text))
    frames.update(_FRAME_INTO.findall(text))
    for frame_name, declaration in _FRAME_CREATE.findall(text):
        frames.add(frame_name)
        for identifier in _DECLARED_IDENTIFIER.findall(declaration):
            lowered = identifier.lower()
            if lowered in _STORAGE_TYPES or re.fullmatch(r"str(?:L|[1-9][0-9]*)", identifier, re.I):
                continue
            if lowered in {"if", "in"}:
                break
            variables.add(identifier)

    locals_found = set(_LOCAL_DECLARATION.findall(text))
    locals_found.update(_LOCAL_REFERENCE.findall(text))
    locals_found.update(tempvars)
    locals_found.update(tempfiles)
    locals_found.update(tempnames)

    globals_found = set(_GLOBAL_DECLARATION.findall(text))
    for braced, plain in _GLOBAL_REFERENCE.findall(text):
        globals_found.add(braced or plain)

    return SymbolIndex(
        variables=sorted_union(variables),
        locals=sorted_union(locals_found),
        globals=sorted_union(globals_found),
        programs=sorted_union(_PROGRAM_DECLARATION.findall(text)),
        tempvars=sorted_union(tempvars),
        tempfiles=sorted_union(tempfiles),
        tempnames=sorted_union(tempnames),
        frames=sorted_union(frames),
    )


def detect_context(line_before_cursor: str) -> CompletionContext:
    """Classify what the caret is completing from the current logical line."""

    # An unfinished macro reference can occur inside a quoted file path.  It
    # must win over the broader path context while the macro name is typed.
    local_match = _LOCAL_CONTEXT.search(line_before_cursor)
    if local_match:
        return CompletionContext("local", local_match.group(1))

    global_match = _GLOBAL_CONTEXT.search(line_before_cursor)
    if global_match:
        return CompletionContext("global", global_match.group(1))

    path_match = _PATH_CONTEXT.search(line_before_cursor)
    if path_match:
        return CompletionContext("path", path_match.group(1) or path_match.group(2) or "")

    # A colon introduces the command governed by prefixes such as by:, svy:,
    # statsby:, bootstrap:, and collect:.  Semicolons can introduce a command
    # when the file uses #delimit ;.
    command_tail = re.split(r"[:;]", line_before_cursor)[-1]
    command_match = _PREFIX_AT_END.fullmatch(command_tail)
    if command_match:
        return CompletionContext("command", command_match.group(1) or "")

    return CompletionContext("symbol", _trailing_identifier(line_before_cursor))


def _trailing_identifier(text: str) -> str:
    match = re.search(r"([A-Za-z_][A-Za-z0-9_]*)$", text)
    return match.group(1) if match else ""


def path_extensions(line_before_cursor: str) -> Optional[Tuple[str, ...]]:
    lowered = line_before_cursor.lower()
    if re.search(r"\b(?:use|save)\b|\b(?:merge|append)\b.*\busing\b", lowered):
        return (".dta",)
    if re.search(r"\b(?:do|run|include)\b", lowered):
        return (".ado", ".do", ".doh")
    if re.search(r"\b(?:import|export)\s+excel\b", lowered):
        return (".xls", ".xlsx")
    if re.search(r"\b(?:import|export)\s+delimited\b", lowered):
        return (".csv", ".tab", ".tsv", ".txt")
    if re.search(r"\b(?:import|export)\s+parquet\b", lowered):
        return (".parquet",)
    return None


def symbol_candidates(index: SymbolIndex, kind: str, fragment: str = "") -> List[Candidate]:
    if kind == "local":
        return _named_candidates(index.locals, fragment, "local macro", "variable")
    if kind == "global":
        return _named_candidates(index.globals, fragment, "global macro", "variable")
    values = sorted_union(
        index.variables,
        index.locals,
        index.globals,
        index.programs,
        index.frames,
    )
    return _named_candidates(values, fragment, "buffer/project symbol", "variable")


def command_candidates(
    commands: Iterable[str], fragment: str = "", annotation: str = "Stata command"
) -> List[Candidate]:
    return _named_candidates(commands, fragment, annotation, "command")


def _named_candidates(
    values: Iterable[str], fragment: str, annotation: str, kind: str
) -> List[Candidate]:
    needle = fragment.casefold()
    return [
        Candidate(value, value, annotation, kind)
        for value in sorted_union(values)
        if not needle or value.casefold().startswith(needle)
    ]


def normalize_roots(paths: Iterable[str]) -> Tuple[str, ...]:
    roots = []
    seen = set()
    for raw_path in paths:
        if not raw_path:
            continue
        path = os.path.abspath(os.path.expandvars(os.path.expanduser(raw_path)))
        if path not in seen and os.path.isdir(path):
            seen.add(path)
            roots.append(path)
    return tuple(roots)


def minimal_roots(paths: Iterable[str]) -> Tuple[str, ...]:
    """Remove nested roots when recursively scanning the same project tree."""

    roots = normalize_roots(paths)
    return tuple(
        path
        for path in roots
        if not any(
            path != other and _contains_path(other, path)
            for other in roots
        )
    )


def _contains_path(parent: str, child: str) -> bool:
    try:
        return os.path.commonpath((parent, child)) == parent
    except ValueError:
        return False


def discover_ado_commands(paths: Iterable[str], max_files: int = 2000) -> Tuple[str, ...]:
    """Find user/project commands with a bounded, short-lived scan cache."""

    roots = minimal_roots(paths)
    signatures = tuple((root, _directory_mtime(root)) for root in roots)
    # A root directory's mtime does not change when a file is added inside an
    # existing child directory.  The epoch bounds that otherwise-indefinite
    # staleness while still sharing scans across completion requests as a user
    # types.  The LRU bound prevents old epochs from accumulating.
    cache_epoch = int(time.monotonic() / ADO_CACHE_TTL_SECONDS)
    return _discover_ado_commands(signatures, max_files, cache_epoch)


def _directory_mtime(path: str) -> int:
    try:
        return os.stat(path).st_mtime_ns
    except OSError:
        return 0


@lru_cache(maxsize=16)
def _discover_ado_commands(
    root_signatures: Tuple[Tuple[str, int], ...], max_files: int, _cache_epoch: int
) -> Tuple[str, ...]:
    """Cached implementation keyed by roots, mtimes, and a short TTL epoch."""

    commands: Set[str] = set()
    visited = 0
    for root, _mtime_ns in root_signatures:
        for current_root, directories, filenames in os.walk(root):
            directories[:] = sorted(
                directory
                for directory in directories
                if directory not in IGNORED_DIRECTORIES and not directory.startswith(".")
            )
            for filename in sorted(filenames):
                if not filename.lower().endswith(".ado"):
                    continue
                visited += 1
                if visited > max_files:
                    return sorted_union(commands)
                name = filename[:-4]
                if re.fullmatch(IDENTIFIER, name) and not name.startswith("_"):
                    commands.add(name)
    return sorted_union(commands)


def read_project_sources(
    paths: Iterable[str], max_files: int = 120, max_total_bytes: int = 1_500_000
) -> Tuple[str, ...]:
    """Read a bounded set of source files for project symbol completion."""

    texts: List[str] = []
    total_bytes = 0
    visited = 0
    for root in minimal_roots(paths):
        for current_root, directories, filenames in os.walk(root):
            directories[:] = sorted(
                directory
                for directory in directories
                if directory not in IGNORED_DIRECTORIES and not directory.startswith(".")
            )
            for filename in sorted(filenames):
                if not filename.lower().endswith(SOURCE_SUFFIXES):
                    continue
                path = os.path.join(current_root, filename)
                try:
                    size = os.path.getsize(path)
                except OSError:
                    continue
                if size > 500_000 or total_bytes + size > max_total_bytes:
                    continue
                try:
                    texts.append(_read_source(path, os.stat(path).st_mtime_ns, size))
                except (OSError, UnicodeError):
                    continue
                total_bytes += size
                visited += 1
                if visited >= max_files:
                    return tuple(texts)
    return tuple(texts)


@lru_cache(maxsize=512)
def _read_source(path: str, _mtime_ns: int, _size: int) -> str:
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def index_sources(texts: Iterable[str]) -> SymbolIndex:
    combined = SymbolIndex()
    for text in texts:
        combined = combined.merged(extract_symbols(text))
    return combined


def path_candidates(
    fragment: str,
    roots: Iterable[str],
    extensions: Optional[Sequence[str]] = None,
    max_results: int = 100,
) -> List[Candidate]:
    """Return relative path entries rooted at the active/project directories."""

    fragment = fragment.replace("\\", "/")
    parent_fragment, _, leaf = fragment.rpartition("/")
    allowed = {suffix.casefold() for suffix in extensions or ()}
    candidates = {}

    if os.path.isabs(fragment):
        search_specs = [(Path("/"), fragment.lstrip("/"))]
    else:
        search_specs = [(Path(root), fragment) for root in normalize_roots(roots)]

    for root, relative_fragment in search_specs:
        rel_parent, _, rel_leaf = relative_fragment.rpartition("/")
        directory = root / rel_parent if rel_parent else root
        try:
            entries = sorted(directory.iterdir(), key=lambda item: (not item.is_dir(), item.name.casefold()))
        except OSError:
            continue
        for entry in entries:
            if entry.name.startswith(".") or not entry.name.casefold().startswith(rel_leaf.casefold()):
                continue
            if not entry.is_dir() and allowed and entry.suffix.casefold() not in allowed:
                continue
            insertion = entry.name + ("/" if entry.is_dir() else "")
            display_parent = parent_fragment or rel_parent
            display = (display_parent + "/" if display_parent else "") + insertion
            annotation = "folder" if entry.is_dir() else "file"
            candidates.setdefault(
                display,
                Candidate(display, insertion, annotation, "path", str(entry)),
            )
            if len(candidates) >= max_results:
                break

    return sorted(
        candidates.values(),
        key=lambda candidate: (candidate.annotation != "folder", candidate.trigger.casefold()),
    )


def dedupe_candidates(candidates: Iterable[Candidate], limit: int = 300) -> List[Candidate]:
    result = []
    seen = set()
    for candidate in candidates:
        key = (candidate.trigger.casefold(), candidate.completion)
        if key in seen:
            continue
        seen.add(key)
        result.append(candidate)
        if len(result) >= limit:
            break
    return result
