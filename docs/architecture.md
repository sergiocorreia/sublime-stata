# Architecture

## Package layers

- `stata.py` is editor-independent execution logic: selection extraction, delimiter and path handling,
  strict dataset-I/O transforms, secure temporary files, build pointers, X11 discovery/delivery, and a
  lazy Windows Automation adapter. It can be unit-tested without importing Sublime.
- `stata_plugin.py` is the thin Sublime command layer. It reads views and settings, owns target pins,
  schedules blocking work away from the UI thread, and exposes the five public commands.
- `stata_completions.py` uses Sublime's deferred `CompletionList`; pure indexing, filesystem bounds,
  catalog loading, and candidate construction live in `completions/catalog.py`.
- `Stata.sublime-syntax` and `Mata.sublime-syntax` are version-2 structural grammars. Official command
  names improve completions, but arbitrary commands are highlighted by command position.
- `misc/generate_stata_catalog.py` and the installed Stata ADO/help trees produce the deterministic
  checked-in command baseline.

## Execution flow

1. `stata_exec` snapshots the buffer and selections on Sublime's UI thread.
2. Pure helpers expand/merge lines, choose a working directory and active delimiter, and wrap raw Mata
   when necessary.
3. An asynchronous callback creates one private temporary do-file.
4. The platform coordinator selects the isolated Linux or Windows backend.
5. Linux discovers visible candidates, validates a pin or chooses the topmost candidate, and performs
   exactly one configured delivery sequence.
6. The temporary file remains available for asynchronous Stata execution and is eligible for cleanup
   only after 24 hours.

There is no automatic Stata launch, batch fallback, clipboard transport, live-session completion
protocol, Wayland backend, or macOS execution backend.

## Safety boundaries

- External commands are always invoked with argument arrays and never through a shell.
- Only a one-line `do` or `help` command is injected; source contents are never typed or logged.
- Stale pins and reused X11 IDs fail closed.
- Delivery modes never retry one another.
- Restoration failure warns that code may already have been sent.
- Temporary cleanup requires an exact generated filename, a regular file, sufficient age, and current
  ownership.

See [Linux execution](linux-execution.md), [Development and validation](development.md), and
[Catalog regeneration](catalog-regeneration.md) for operational details.
