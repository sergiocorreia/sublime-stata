# Regenerating the Stata command catalog

`completions/stata19_commands.json` is the offline baseline used for command
completion. It was generated from the installed StataNow 19.5 tree updated on
12 August 2026. Completion never starts Stata or queries a live Stata session.

## Selection policy

The generator uses three reviewable sources:

1. A public ado command must have a program declaration in an `.ado` file and
   either a same-named `.sthlp` entry or an official `*help_alias.maint` mapping
   to a shared help page with explicit `{cmd:...}`/`{opt ...}` syntax markup.
   The shared-page path captures commands such as `pwcorr`, `avplot`, and
   `hettest` without admitting every help topic or legal abbreviation.
2. `VALIDATED_BUILTIN_OR_DISPATCHER_COMMANDS` and
   `GUARANTEED_MODERN_COMMANDS` in the generator explicitly add executable
   commands and public ado dispatchers that are not reliably captured by the
   file-derived documentation rules, such as `predict`, `estat`, `collect`, and
   `lateffects`. These allowlists are unioned after helper filtering, so an
   explicitly validated public dispatcher cannot be filtered out by its name.
   The same reviewed list retains a few stable, high-use official aliases such
   as `su`, `tab`, and `di` without reintroducing every historical abbreviation.
3. Derived underscored ado names are private dispatchers by default (for example,
   public `import delimited` is not a top-level `import_delimited` command).
   Reviewed public programmer commands such as `mat_capp`, `mat_rapp`, and
   `mat_order` live in the explicit allowlist. Helper-name rules and
   `DENIED_ADO_COMMANDS` remove other technical, generated, and obsolete
   subroutines.

Both `ado/base` and `ado/updates` are scanned when present. The metadata in the
generated JSON records whether an updates directory was found and the counts
from each explicit source.

## Generate and verify

From the repository root, run:

```bash
python3 misc/generate_stata_catalog.py --stata-root /usr/local/stata19
python3 misc/generate_stata_catalog.py --stata-root /usr/local/stata19 --check
python3 -m unittest discover -s tests -p 'test_*.py'
```

Use a different `--stata-root` when Stata is installed elsewhere. Review changes
to both the command list and its metadata before committing them. When a newly
documented executable dispatcher is missing, add it to the appropriate explicit
allowlist. Add a command to the denylist only when its installed help describes
it as an implementation detail rather than a user-facing command.
