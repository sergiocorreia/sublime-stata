# Completions and snippets

## Command catalog

Command-position completion combines the checked-in StataNow 19.5 catalog with project commands and
declared programs. The generated baseline records the Stata version and revision used to build it;
catalog regeneration is documented separately in
[Catalog regeneration](catalog-regeneration.md).

Curated rich entries add option-aware templates for modern Stata commands and common research tools.
The syntax grammar does not rely on a giant fixed command regular expression: a user-written or newly
installed command still receives command-position highlighting even before it appears in the catalog.

## Contextual symbols

Sublime's deferred completion API indexes source text and files off the UI thread. Suggestions include:

- locals, globals, `tempvar`, `tempfile`, and `tempname` declarations;
- simple generated, input, cloned, and renamed variables;
- frames and declared programs from the current buffer, other open Stata views, and bounded project
  source scans;
- public `*.ado` filenames from the project, standard personal ADO locations, and `ado_paths`;
- relevant `.do`, `.ado`, `.doh`, and `.dta` paths when completing a file-taking command.

The package deliberately does not query a running Stata GUI for variables or live session state.

## Project-aligned snippets

Snippet expansions follow `extra/STATA_STYLE_GUIDE.md`: literal tabs, lowercase placeholders,
unabbreviated `forvalues` and `rename`, explicit storage types and merge checks, compact `mi()`,
frames for accumulated results, and preferred tools such as `gisid`, `gegen`, `reghdfe`, `ppmlhdfe`,
and `rangestat`.

The most useful triggers are listed in [Usage and settings](usage.md#snippet-triggers). The files in
`extra/` are references only; completions and snippets do not source or install `common.do`, `dodo.ado`,
the graph scheme, or the sound file.

## Frequency-informed ordering

Completion ordering stores only two compact command-name tiers: commands observed in at least 40% of
projects and commands observed in 10–40%. Everything else uses the default/infrequent tier. Counts and
project-level source data are not distributed. Common abbreviations are mapped to their full commands
before tiering, while the original abbreviation is retained when it is itself a supported completion.

To rebuild the snapshot locally from the ignored private aggregate, run:

```sh
python3 misc/generate_command_tiers.py --input extra/cmd_count.csv
```

Snippets always precede command-name tiers. The `command_priorities` setting can place personal choices
ahead of the bundled ordering without copying the frequency table into settings.
